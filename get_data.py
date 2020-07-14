"""
A collection of functions to process the data & prepare a json file so blender can read it directly
"""

import pandas as pd
import numpy as np
import json,os,glob,arrow

def make_df_indv(file,data_type):
    '''
    Given file name, ingest the data and return a clean df
    '''

    data_raw = pd.read_csv(file)

    # Filter out unwanted cols
    drop_col = data_raw.filter(regex='Previous|Total').columns
    data_raw = data_raw.drop(drop_col,axis=1)
    col_filtered = list(data_raw.filter(regex=data_type).columns)
    col_filtered.insert(0,'Small Unit Installation Postcode')
    data = data_raw[col_filtered]

    # Clean the entry format a bit
    data = data.applymap(lambda s:float(str(s).replace(',','')))

    # Clean up the column name
    time_format = 'YYYY-MM'
    new_col = [arrow.get(item[:8],'MMM YYYY').format(time_format)
        for item in col_filtered[1:]]
    new_col.insert(0,'postcode')
    data.columns = new_col
    data.dropna(inplace=True)

    return data

def make_df_per_source(source,data_type,cumsum=True,agg_on_postcode=True):
    '''
    Get data from all the files, given a source, and merge all together
    '''
    raw_dir = os.path.join('data','raw')
    file_list = glob.glob(os.path.join(raw_dir,f'*{source}.csv'))

    df = make_df_indv(file_list[0],data_type)
    for file in file_list[1:]:
        df_ = make_df_indv(file,data_type)
        df = df.merge(df_,left_on='postcode', right_on='postcode',how='outer')
    df = df.apply(lambda s:s.fillna(0.0))

    # remove the duplicated cols, rename the remaining and sort them
    df.drop(df.filter(regex='x').columns,axis=1,inplace=True)
    new_col = []
    for col in df.columns:
        if 'y' in col:
            col = col.split('_')[0]
            new_col.append(col)
        else:
            new_col.append(col)
    df.columns = new_col
    df = df.reindex(sorted(df.columns), axis=1)

    if cumsum:
        df = pd.concat([df[['postcode']],
                          df.drop(['postcode'],axis=1).cumsum(axis=1)],axis=1)
    if agg_on_postcode:
        df['postcode'] = df.postcode.apply(lambda s:str(int(s)).zfill(4)[:2])
        df = df.groupby(by='postcode').sum().reset_index()

    # convert to melt format so other app can take it
    df = df.melt(id_vars=['postcode'])
    df.columns = ['postcode','time',f'{source}-{data_type}']

    return df

def make_df(source_list,data_type,cal_all=True,cumsum=True,agg_on_postcode=True):
    '''
    combine all different sources, and get a sum col for all
    '''

    df_all = make_df_per_source(source_list[0],data_type,cumsum=cumsum,agg_on_postcode=agg_on_postcode)
    print(f'Getting data for {source_list[0]} - {data_type}')

    for source in source_list[1:]:
        df_all_ = make_df_per_source(source,data_type)
        df_all_ = df_all_.apply(lambda s:s.fillna(0.0))
        df_all = df_all.merge(df_all_,on=['postcode','time'],how='outer')

        print(f'Getting data for {source} - {data_type}')

    df_all.dropna(axis=1,inplace=True,how='all')

    if cal_all:
        df_all['All-Installations'] = df_all.iloc[:,2:].sum(axis=1)

    df_all = df_all.apply(lambda s:s.fillna(0.0))
    df_all = pd.melt(df_all,id_vars=['postcode','time'])
    if data_type == 'Installations':
        df_all.columns = ['postcode','date','source_type','install_num']
        df_all.source_type = df_all.source_type.apply(lambda s: s.replace('-Installations',''))
    else:
        df_all.columns = ['postcode','date','source_type','total_output']
        df_all.source_type = df_all.source_type.apply(lambda s: s.replace('-Output',''))

    return df_all

def data_for_bl(data_out):
    """
    Process the data for blender and dump into a json file.
    The json file contains original data as well as scaled data so blender can use them directly.
    'height' & 'color' are scaled between 0 & 1 so it can be used as a factor for color gradient.
    """
    install = make_df(['SGU-Solar'],'Installations',cal_all=False,cumsum=True,agg_on_postcode=True)
    output = make_df(['SGU-Solar'],'Output',cal_all=False,cumsum=True,agg_on_postcode=True)

    data = dict() # master data dict
    postcode_list = install.postcode.unique().tolist()
    for postcode in postcode_list:
        date_list = install[install.postcode == postcode].date.to_list()
        install_list = install[install.postcode == postcode].install_num.apply(int).to_list()
        height_list = [num / install.install_num.max() for num in install_list]
        output_list = output[output.postcode == postcode].total_output.apply(float).to_list()
        color_list = [num / output.total_output.max() for num in output_list]

        data_ = dict() # data dict for each postcode
        data_['date'] = [arrow.get(d,'YYYY-MM').format('MMM YYYY')
                        for d in date_list]
        data_['height'] = height_list
        data_['color'] = color_list
        data_['install'] = ['{:,}'.format(i) for i in install_list]
        data_['output'] = ['{:,.2f}'.format(f/1000) for f in output_list]

        data[postcode] = data_

    # add an 'all' postcode entry for the sum data
    install_all = install.groupby(by = 'date').sum().install_num.apply(int).to_list()
    output_all = output.groupby(by = 'date').sum().total_output.apply(float).to_list()

    data_ = dict()
    data_['date'] = [arrow.get(d,'YYYY-MM').format('MMM YYYY')
                        for d in date_list]
    data_['install'] = ['{:,}'.format(i) for i in install_all]
    data_['output'] = ['{:,.2f}'.format(f/1000) for f in output_all]

    data['all'] = data_

    with open(data_out,'w') as f:
        json.dump(data, f)

    return data

if __name__ == '__main__':
    data_out = os.path.join('output','data.json')
    data_for_bl(data_out)
