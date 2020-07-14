"""
A collection of functions to simplify and aggerate geo data, and output a shapefile for blender to use
"""

import pandas as pd
import numpy as np
import json,os,geopandas
import topojson as tp
from pytopojson import feature

def simplify_geo(geo_series,simplify_with,simplify_algorithm,tolerance,geojson_out):
    """
    Use topojson to simplify to minimize the gap/overlay among the border
    This can take a lot of RAM, depending on how complicated the input geometries are

    """
    print('Simplifying geometry...')
    geo_series = geo_series.simplify(tolerance=0.005,preserve_topology=True)
    # The preliminary simplify is needed so RAM needed for next step is reduced
    # The unit in tolerance is in degree
 
    topo = tp.Topology(geo_series,
                       topology=True,
                       simplify_with=simplify_with,
                       simplify_algorithm=simplify_algorithm,
                       toposimplify=tolerance
                      )
    topo_out = os.path.join('output',f'geo.topo.json')
    topo.to_json(topo_out)

    # Topojson doesn't have a way to convert back to geojson, using pytopojson
    with open(topo_out) as f:
        topo_ = f.read()
        f.close()

    topo_ = json.loads(topo_)
    feature_ = feature.Feature()
    geojson = feature_(topo_, 'data')
    os.remove(topo_out)

    with open(geojson_out, "w") as outfile:
        json.dump(geojson, outfile)
        outfile.close()

def get_geo(geojson_out,agg_on_postcode=True,simplify=True,remove_remote=True,tolerance=0.002):
    '''
    get the GeoJson file based on Aussie postcodes, can be aggerated to a 2 digit format
    this won't include some postcodes, like PO boxes
    '''

    print('Loading shapefile...')
    shp_file = os.path.join('data','shp','poa_2016_aust_shape.zip')
    geo = geopandas.read_file(f"""zip://{shp_file}""")
    geo = geo.dropna()
    geo = geo[['POA_CODE16','geometry']]
    geo.columns=['postcode','geometry']
    postcode = geo[['postcode']]

    # drop out the remote offshore territories so they don't show up in the final map
    # if the data is aggerated, their data should not be lost
    if remove_remote:
        print('Removing remote locations...')
        offshore_list = ['6798','6799','2899','7151']
        geo = geo.drop(geo.loc[geo['postcode'].isin(offshore_list)].index).reset_index(drop=True)
        postcode = geo[['postcode']]

    if agg_on_postcode:
        print('Performing aggregation...')
        geo['postcode'] = geo['postcode'].apply(lambda s:s[:2])
        geo = geo[['geometry','postcode']].dissolve(by='postcode', aggfunc='sum')
        geo.reset_index(inplace=True)
        postcode = geo[['postcode']] # replace previous one

    if simplify:
        simplify_geo(geo_series = geo.geometry,
                     simplify_with = 'simplification',
                     simplify_algorithm = 'vw',
                     tolerance = tolerance,
                     geojson_out = geojson_out)

        geo = geopandas.read_file(geojson_out)
        geo = pd.concat([geo,postcode],axis=1)
        geo.to_file(geojson_out, driver='GeoJSON')

    else:
        geo.to_file(geojson_out, driver='GeoJSON')

    print('All done!')
    return geo

def make_shp_bl(shp_out, geojson_out, base_height):
    """
    Convert the geojson to shapefile & add a base_height columns for blender to extrude
    """
    geo = get_geo(geojson_out,
                  agg_on_postcode=True,
                  simplify=True,
                  remove_remote=True,
                  tolerance=0.002)
    geo['base'] = base_height
    geo.to_file(shp_out)

if __name__ == '__main__':
    shp_out = os.path.join("output","geo.shp")
    geojson_out = os.path.join('output','geo.geojson')

    make_shp_bl(shp_out, geojson_out, base_height=0.5)
    os.remove(geojson_out)
