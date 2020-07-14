# Small-scale Solar PVs Installation: Data Visualisation with Blender & Python 

In this project, I made a 3D time-series choropleth map in Blender programmatically using Blender's Python API.

![](./resource/data-viz.gif)

Check out the final render video [here](https://youtu.be/7xwRgUXbkV8) and an interactive web version [here](https://hengwang322.github.io/viz.html).

Data is from [Clean Energy Regulator](http://www.cleanenergyregulator.gov.au/RET/Forms-and-resources/Postcode-data-for-small-scale-installations), and the original Shapefile for postal area boundaries in Australia (ASGS Ed 2016) is from [Australian Bureau of Statistics](https://www.abs.gov.au/AUSSTATS/abs@.nsf/DetailsPage/1270.0.55.003July%202016?OpenDocument). These files are provided in the `data` directory. 

# Usage
1. Clone the repository
2. Install [Blender](https://www.blender.org/download/), [BlenderGIS addon](https://github.com/domlysz/BlenderGIS), and necessary python packages via:

 ```shell
 $ pip install --upgrade -r requirements.txt
 ```

3. Process data

- You can run the `get_data.py` script directly, which generates `data.json` in `output` that contains the data for installation quantity for solar PVs (Small generation unit, or SGU).
- Alternatively, you can import the script as a module. The module contains some useful functions, for example:

```
from get_data import make_df

# these are all possible sources
source_list =  ['SWH-Solar',
                'SWH-Air-source-heat-pump',
                'SGU-Wind',
                'SGU-Solar',
                'SGU-Hydro']

# only types available are 'Installations' and 'Output'
source_type = 'Installations'

# this returns a pandas dataframe in a melt format
df = make_df(source_list,
             source_type,
             cal_all=True, # Add a column that sums all time number in a postcode
             cumsum=True, # calculate cumulative sum
             agg_on_postcode=True # Aggregate to 2 digit postcode
             )
```

4. Process Shapefile

- You can run the `get_shp.py` script directly, which generates `geo.shp` in `output` that contains simplified 2-digit postcode area boundaries in Australia.
- Alternatively, you can import the script as a module. The module contains some useful functions, for example:

```
from get_shp import get_geo

# this will return a geopandas dataframe
geo = get_geo(geojson_out='./output.geojson',
              agg_on_postcode=True, # Aggregate to 2 digit postcode
              remove_remote=True, # remove remote offshore postcodes
              simplify=True, # Simplify geometry
              tolerance=0.002 # Tolerance for simplification, in degrees
              )
```

5. Build blender scene using its Python API.

`build_scene.py` is run inside Blender to build the whole scene: 
![](./resource/blender_usage.gif)

