"""
This script is written and tested in Blender 2.83.1 & BlenderGIS 1.0
"""

import bpy, bmesh, json, os, re
from pathlib import Path

def load_data(data_file):
    with open(data_file) as f:
        data = json.load(f)
        f.close()
    return data

def clean_mesh(obj_name):
    # Clean up the mesh by delete some rogue vertices
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    obj = bpy.data.objects[obj_name]
    me = obj.data
    wm = obj.matrix_world
    bpy.context.view_layer.objects.active = obj
    
    bm = bmesh.from_edit_mesh(me)
    bm.select_mode = {'VERT'}
    for v in bm.verts:
        global_v = wm @ v.co # calculate global coordinates for the vertex
        v.select = ( global_v.x < -20 and global_v.y <-16) 
    bm.select_flush_mode()
    me.update()
    bpy.ops.mesh.delete()
        
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        
def add_geo_obj(shp_file):
    # the objects & names in collection 'geo' will be referenced throughout the script
    try:
        bpy.ops.importgis.shapefile(filepath=shp_file,
                                    fieldExtrudeName="base",
                                    extrusionAxis='Z',
                                    separateObjects=True,
                                    fieldObjName="postcode"
                                    )
    except AttributeError:
        print("Cannot seem to find Blender GIS addon. Make sure it's installed and enabled.")
        
    for obj in bpy.data.collections['geo'].all_objects:
        clean_mesh(obj.name)
         
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects['59'].select_set(True)
    bpy.ops.object.delete() 

def add_material(obj_name):
    gradient_color0 = (0.05,0.05,0.05,1) # dark grey
    gradient_color1 = (0.1,2,0,1) # green, also control emission strength, that's why green is > 1

    bpy.context.view_layer.objects.active = bpy.data.objects[obj_name]
    obj = bpy.data.objects[obj_name]
    bpy.context.view_layer.objects.active = obj
    mat = bpy.data.materials.new(name=obj_name)
    obj.data.materials.append(mat)
    mat.use_nodes = True
    bpy.context.object.active_material.blend_method = 'BLEND'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    output = nodes.get('Material Output')
    output.location = (300,0)

    bsdf = nodes.get('Principled BSDF')
    bsdf.location = (0,0)
    bsdf.inputs[18].default_value = 0.5 # alpha
    bsdf.inputs[15].default_value = 1.0 # transmission
    links.new(bsdf.outputs[0],output.inputs[0]) # BSDF to material surface

    # add color ramp as input for main shader to get a color gradiant
    color_ramp = nodes.new("ShaderNodeValToRGB")
    color_ramp.location = (-300,0)
    links.new(color_ramp.outputs[0],bsdf.inputs[0]) # color ramp to base color
    links.new(color_ramp.outputs[0],bsdf.inputs[17]) # color ramp to emission color/strength

    color_ramp.color_ramp.elements[0].color = gradient_color0
    color_ramp.color_ramp.elements[1].color = gradient_color1
    
    # the value node will be used for inserting keyframes
    color_v = nodes.new("ShaderNodeValue")
    color_v.location = (-600,0)
    links.new(color_v.outputs[0],color_ramp.inputs[0]) # value node to ramp's color 

def add_material_all(collection):
    for obj in bpy.data.collections[collection].all_objects:
        add_material(obj.name)

def add_shape_key(obj_name,max_height):
    obj = bpy.data.objects[obj_name]
    me  = obj.data
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shape_key_add(from_mix=False) # Base Key
    bpy.ops.object.shape_key_add(from_mix=False) # Key 1
    bpy.context.object.active_shape_key_index = 1
    bpy.data.shape_keys["Key"].name = obj_name

    bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    bm = bmesh.from_edit_mesh(me)
    bm.select_mode = {'VERT'}
    for v in bm.verts:
        if v.co.z > 0: #since the base is at 0, this will effectively select top faces
            v.co.z = max_height 
        
    bm.select_flush_mode()
    me.update()

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

def add_shape_key_all(max_height,collection):
    for obj in bpy.data.collections[collection].all_objects:
        add_shape_key(obj.name,max_height=max_height)
            
def animate_obj_all(frame_step,data):
    data_len = len(data['all']['date'])
    bpy.context.scene.frame_end = data_len*frame_step

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    bpy.context.view_layer.objects.active = None

    for keyframe_id in range(data_len):
        for obj in bpy.data.collections['geo'].all_objects:
            height = data[obj.name[:2]]['height'][keyframe_id] 
            # height values are scaled between 0 & 1, and are used for inserting keyframes
            shapekey = bpy.data.shape_keys[obj.name].key_blocks["Key 1"]
            shapekey.value = height
            shapekey.keyframe_insert(data_path="value", frame=frame_step*keyframe_id)
    
def animate_material_all(frame_step,data):
    data_len = len(data['all']['date'])
    bpy.context.scene.frame_end = data_len*frame_step

    for keyframe_id in range(data_len):
        for mat in bpy.data.materials:
            if mat.name in [obj.name for obj in bpy.data.collections['geo'].all_objects]:
                color = data[mat.name]['color'][keyframe_id]
                color_value = mat.node_tree.nodes["Value"].outputs[0]
                color_value.default_value = color
                color_value.keyframe_insert('default_value',frame=frame_step*keyframe_id)

def add_camera(lens):
    cam = bpy.data.cameras.new("Camera")
    cam.lens = lens
    cam_obj = bpy.data.objects.new("Camera", cam)
    bpy.context.scene.collection.objects.link(cam_obj)

def animate_camera(frame_step,data):
    data_len = len(data['all']['date'])
    camera = bpy.data.objects['Camera']

    # pan down camera a bit at first, then a lot in the end 
    camera.location = (0,4,40)
    camera.rotation_euler = (0,0,0)
    camera.keyframe_insert(data_path="location", frame=0)
    camera.keyframe_insert(data_path="rotation_euler", frame=0)
 
    camera.location = (0,-4.6,40.17)
    camera.rotation_euler = (0.175,0,0)
    camera.keyframe_insert(data_path="location", frame=int(frame_step*data_len*0.5))
    camera.keyframe_insert(data_path="rotation_euler", frame=int(frame_step*data_len*0.5))

    camera.location = (0,-19.25,30.57)
    camera.rotation_euler = (0.534,0,0)
    camera.keyframe_insert(data_path="location", frame=int(frame_step*data_len*0.75))
    camera.keyframe_insert(data_path="rotation_euler", frame=int(frame_step*data_len*0.75))
    
    camera.location = (0,-22.69,24.64)
    camera.rotation_euler = (0.698,0,0)
    camera.keyframe_insert(data_path="location", frame=int(frame_step*data_len))
    camera.keyframe_insert(data_path="rotation_euler", frame=int(frame_step*data_len))
    
def add_bg_plane(size):
    # Adds a highly reflective background plane
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    bpy.ops.mesh.primitive_plane_add(size=size,enter_editmode=False,location=(0,0,0))

    plane_mat = bpy.data.materials.new(name='plane_mat')
    plane_mat.use_nodes = True
    output = plane_mat.node_tree.nodes.get('Material Output')
    bsdf = plane_mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs[0].default_value = (0.01,0.01,0.01,1) # base color, black
    bsdf.inputs[7].default_value = 0.1 # roughness

    plane_mat.node_tree.links.new(bsdf.outputs[0],output.inputs[0]) # bsdf to material surface
    bpy.data.objects['Plane'].data.materials.append(plane_mat)

def animate_text(font_path,frame_step,data):
    title_loc = (-38.9,24.5,0)
    cap1_loc = (-29.784,-9.944,0)
    cap2_loc = (-0.6316,-13.728,0)
    cap3_loc = (-22.052,-15.814,0) 
    cap4_loc = (-3.2,-15.914,0)
    foot_loc = (-30.4412,-16.75,0)

    data_len=len(data['all']['date'])

    title_curve = bpy.data.curves.new(type="FONT",name="title curve")
    title_curve.extrude = 0.01
    title_curve.font = bpy.data.fonts.load(font_file)
    title_curve.body = f"""
                Growth of Small-scale Solar PVs in Australia
                       Quantity & Output by Postcode"""
    title_obj = bpy.data.objects.new("title", title_curve)
    bpy.context.scene.collection.objects.link(title_obj)
    title_obj.location = title_loc
    title_obj.scale = (2,2,2)

    footnote_curve = bpy.data.curves.new(type="FONT",name="footnote curve")
    footnote_curve.extrude = 0.01
    footnote_curve.font = bpy.data.fonts.load(font_file)
    footnote_curve.body = f"""
                        Height represents install quantity, color represents output. Data Source: Clean Energy Regulator
                        """
    footnote_obj = bpy.data.objects.new("footnote", footnote_curve)
    bpy.context.scene.collection.objects.link(footnote_obj)
    footnote_obj.location = foot_loc
    footnote_obj.scale = (0.7,0.7,0.7)

    caption1_curve = bpy.data.curves.new(type="FONT",name="caption1")
    caption1_curve.extrude = 0.01
    caption1_curve.font = bpy.data.fonts.load(font_file)
    caption1_curve.space_line = 1.6
    caption1_obj = bpy.data.objects.new("caption1", caption1_curve)
    bpy.context.scene.collection.objects.link(caption1_obj)
    caption1_obj.location = cap1_loc
    caption1_obj.scale = (1.1,1.2,1.2)

    caption2_curve = bpy.data.curves.new(type="FONT",name="caption2")
    caption2_curve.extrude = 0.01
    caption2_curve.font = bpy.data.fonts.load(font_file)
    caption2_obj = bpy.data.objects.new("caption2", caption2_curve)
    bpy.context.scene.collection.objects.link(caption2_obj)
    caption2_obj.location = cap2_loc
    caption2_obj.scale = (2,2.2,2.2)

    caption3_curve = bpy.data.curves.new(type="FONT",name="caption3")
    caption3_curve.extrude = 0.01
    caption3_curve.font = bpy.data.fonts.load(font_file)
    caption3_curve.body = """Raising the total power output to"""
    caption3_obj = bpy.data.objects.new("caption3", caption3_curve)
    bpy.context.scene.collection.objects.link(caption3_obj)
    caption3_obj.location = cap3_loc
    caption3_obj.scale = (1.1,1.2,1.2)

    caption4_curve = bpy.data.curves.new(type="FONT",name="caption4")
    caption4_curve.extrude = 0.01
    caption4_curve.font = bpy.data.fonts.load(font_file)
    caption4_obj = bpy.data.objects.new("caption4", caption4_curve)
    bpy.context.scene.collection.objects.link(caption4_obj)
    caption4_obj.location = cap4_loc
    caption4_obj.scale = (2,2.2,2.2)

    # add white static material
    font_mat = bpy.data.materials.new(name='font_mat')
    font_mat.use_nodes = True
    output = font_mat.node_tree.nodes.get('Material Output')
    bsdf = font_mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs[17].default_value = (2,2,2,1) # emission color/strength
    font_mat.node_tree.links.new(bsdf.outputs[0],output.inputs[0]) # bsdf to material surface

    bpy.data.objects['title'].data.materials.append(font_mat)
    bpy.data.objects['caption1'].data.materials.append(font_mat)
    bpy.data.objects['footnote'].data.materials.append(font_mat)

    # add green animated material
    font_green_mat = bpy.data.materials.new(name='font_green_mat')
    font_green_mat.use_nodes = True
    output_green = font_green_mat.node_tree.nodes.get('Material Output')
    bsdf_green = font_green_mat.node_tree.nodes.get('Principled BSDF')

    font_green_mat.node_tree.links.new(bsdf_green.outputs[0],output_green.inputs[0]) # bsdf to material surface

    color_ramp_font = font_green_mat.node_tree.nodes.new("ShaderNodeValToRGB")
    color_ramp_font.location = (-300,0)
    font_green_mat.node_tree.links.new(color_ramp_font.outputs[0],bsdf_green.inputs[0]) # ramp to base color
    font_green_mat.node_tree.links.new(color_ramp_font.outputs[0],bsdf_green.inputs[17]) # ramp to emission color/strength

    color_ramp_font.color_ramp.elements[0].color = (2,2,2,1) # white
    color_ramp_font.color_ramp.elements[1].color = (0.1,2,0,1) # green

    color_v_font = font_green_mat.node_tree.nodes.new("ShaderNodeValue")
    color_v_font.location = (-600,0)
    font_green_mat.node_tree.links.new(color_v_font.outputs[0],color_ramp_font.inputs[0]) # value to ramp's color

    bpy.data.objects['title'].data.materials.append(font_mat)
    bpy.data.objects['caption1'].data.materials.append(font_mat)
    bpy.data.objects['caption3'].data.materials.append(font_mat)
    bpy.data.objects['footnote'].data.materials.append(font_mat)

    bpy.data.objects['caption2'].data.materials.append(font_green_mat)
    bpy.data.objects['caption4'].data.materials.append(font_green_mat)

    # animate green text, the text turn green linearly
    mat_green = bpy.data.materials["font_green_mat"]
    color_value = mat_green.node_tree.nodes["Value"].outputs[0]
    color_value.default_value = 0
    color_value.keyframe_insert('default_value',frame=0)
    color_value.default_value = 0.95
    color_value.keyframe_insert('default_value',frame=frame_step*data_len)

    # update text with frames
    def update(self):
        caption1 = bpy.data.objects['caption1']
        caption2 = bpy.data.objects['caption2']
        caption4 = bpy.data.objects['caption4']
        frame = bpy.context.scene.frame_current
        data_index = int(frame/frame_step)
        caption1.location = cap1_loc

        caption1.data.body = \
              f"""
              By {data['all']['date'][data_index]}
              The quantity of solar PVs has grown to
              """
        caption2.location = cap2_loc
        caption2.data.body = f"""{data['all']['install'][data_index]}"""
        caption4.location = cap4_loc
        caption4.data.body = f"""{data['all']['output'][data_index]} MW"""

    if bpy.context.scene.frame_current in range(frame_step*data_len):
        bpy.app.handlers.frame_change_post.append(update)

def build_scene(data_file,shp_file,font_file,frame_step,max_height):
    data = load_data(data_file=data_file)
    
    # Start scene by deleting all objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Add all objects & animate
    add_geo_obj(shp_file=shp_file)
    add_material_all(collection='geo')
    add_shape_key_all(max_height,collection='geo')
    animate_obj_all(frame_step,data)

    add_material_all(collection='geo')
    animate_material_all(frame_step,data)
    
    add_camera(lens=18)
    animate_camera(frame_step,data)
    
    add_bg_plane(size=500)
   
    animate_text(font_file,frame_step,data)    

def update_render_setting():
    # Tweak the rendering settings
    bpy.context.scene.frame_start = 0
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.use_adaptive_sampling = True
    bpy.context.scene.cycles.adaptive_threshold = 0.001
    bpy.context.scene.cycles.use_animated_seed = True
    bpy.context.scene.cycles.samples = 850
    bpy.context.scene.cycles.sample_clamp_direct = 0.2
    bpy.context.scene.cycles.sample_clamp_indirect = 10
    bpy.context.scene.cycles.blur_glossy = 5
    bpy.context.scene.cycles.max_bounces = 4

    bpy.context.scene.world.light_settings.use_ambient_occlusion = True
    
    bpy.context.scene.render.image_settings.color_depth = '16'
    bpy.context.scene.render.tile_x = 256
    bpy.context.scene.render.tile_y = 256
    
    scene = bpy.data.scenes['Scene'].view_layers['View Layer']
    scene.cycles.use_denoising = True
    
    # Setup GPU
    scene = bpy.context.scene
    scene.cycles.device = 'GPU'
    prefs = bpy.context.preferences
    prefs.addons['cycles'].preferences.get_devices()
    cprefs = prefs.addons['cycles'].preferences
    print(cprefs)
    # Attempt to set GPU device types if available
    for compute_device_type in ('CUDA', 'OPENCL', 'NONE'):
        try:
            cprefs.compute_device_type = compute_device_type
            print('Device found',compute_device_type)
            break
        except TypeError:
            pass
    # Enable all CPU and GPU devices
    for device in cprefs.devices:
        if not re.match('intel', device.name, re.I):
            print('Activating',device)
            device.use = True
         
if __name__ == '__main__':
    frame_step = 4 # the steps between keyframes
    max_height = 6
    
    current_dir = Path(bpy.data.filepath).parent # this is where your blend file is saved
    data_file = os.path.join(current_dir,'data.json')
    shp_file = os.path.join(current_dir,'geo.shp')
    # Download the free font at design.ubuntu.com/font/
    font_file = os.path.join(current_dir.parent,'resource','UbuntuMono-Regular.ttf')
    
    build_scene(data_file,shp_file,font_file,frame_step,max_height)
    update_render_setting()