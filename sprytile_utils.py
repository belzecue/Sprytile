import bpy
from mathutils import Matrix, Vector
from bpy.types import Panel
from . import sprytile_modal


def get_grid_matrix(srpytile_grid):
    """Returns the transform matrix of a sprytile grid"""


def get_grid_texture(obj, sprytile_grid):
    mat_idx = obj.material_slots.find(sprytile_grid.mat_id)
    if mat_idx == -1:
        return None
    material = obj.material_slots[mat_idx].material
    if material is None:
        return None
    target_img = None
    for texture_slot in material.texture_slots:
        if texture_slot is None:
            continue
        if texture_slot.texture is None:
            continue
        if texture_slot.texture.type == 'NONE':
            continue
        if texture_slot.texture.type == 'IMAGE':
            # Cannot use the texture slot image reference directly
            # Have to get it through bpy.data.images to be able to use with BGL
            target_img = bpy.data.images.get(texture_slot.texture.image.name)
            break
    return target_img


class SprytileGridAdd(bpy.types.Operator):
    bl_idname = "sprytile.grid_add"
    bl_label = "Add New Grid"

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        self.add_new_grid(context)
        return {'FINISHED'}

    @staticmethod
    def add_new_grid(context):
        grid_array = context.scene.sprytile_grids
        if len(grid_array) < 1:
            return
        grid_idx = context.object.sprytile_gridid
        selected_grid = grid_array[grid_idx]

        new_idx = len(grid_array)
        new_grid = grid_array.add()
        new_grid.mat_id = selected_grid.mat_id
        new_grid.grid = selected_grid.grid
        new_grid.is_main = False

        grid_array.move(new_idx, grid_idx + 1)


class SprytileGridRemove(bpy.types.Operator):
    bl_idname = "sprytile.grid_remove"
    bl_label = "Remove Grid"

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        self.delete_grid(context)
        return {'FINISHED'}

    @staticmethod
    def delete_grid(context):
        grid_array = context.scene.sprytile_grids
        if len(grid_array) <= 1:
            return
        grid_idx = context.object.sprytile_gridid

        del_grid = grid_array[grid_idx]
        del_mat_id = del_grid.mat_id

        # Check the grid array has
        has_main = False
        grid_count = 0
        for idx, grid in enumerate(grid_array.values()):
            if grid.mat_id != del_mat_id:
                continue
            if idx == grid_idx:
                continue
            grid_count += 1
            if grid.is_main:
                has_main = True

        # No grid will be left referencing the material
        # Don't allow deletion
        if grid_count < 1:
            return

        grid_array.remove(grid_idx)
        context.object.sprytile_gridid -= 1
        # A main grid is left, exit
        if has_main:
            return
        # Mark the first grid that references material as main
        for grid in grid_array:
            if grid.mat_id != del_mat_id:
                continue
            grid.is_main = True
            break


class SprytileGridCycle(bpy.types.Operator):
    bl_idname = "sprytile.grid_cycle"
    bl_label = "Cycle grid settings"

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        self.cycle_grid(context)
        return {'FINISHED'}

    @staticmethod
    def cycle_grid(context):
        obj = context.object
        grids = context.scene.sprytile_grids
        curr_grid_idx = obj.sprytile_gridid
        curr_mat_id = grids[curr_grid_idx].mat_id
        next_grid_idx = curr_grid_idx + 1
        if next_grid_idx < len(grids):
            if grids[next_grid_idx].mat_id == curr_mat_id:
                obj.sprytile_gridid = next_grid_idx
        else:
            for grid_idx, check_grid in enumerate(grids):
                if check_grid.mat_id == curr_mat_id:
                    obj.sprytile_gridid = grid_idx
                    break


class SprytileNewMaterial(bpy.types.Operator):
    bl_idname = "sprytile.add_new_material"
    bl_label = "New Shadeless Material"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def invoke(self, context, event):
        obj = context.object

        mat = bpy.data.materials.new(name="Material")
        mat.use_shadeless = True

        set_idx = len(obj.data.materials)
        obj.data.materials.append(mat)
        obj.active_material_index = set_idx

        bpy.ops.sprytile.validate_grids()
        return {'FINISHED'}


class SprytileValidateGridList(bpy.types.Operator):
    bl_idname = "sprytile.validate_grids"
    bl_label = "Validate Material Grids"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        self.validate_grids(context)
        return {'FINISHED'}

    @staticmethod
    def validate_grids(context):
        curr_sel = context.object.sprytile_gridid
        grids = context.scene.sprytile_grids
        mat_list = bpy.data.materials
        remove_idx = []
        print("Material count: %d" % len(bpy.data.materials))

        # Filter out grids with invalid IDs or users
        for idx, grid in enumerate(grids.values()):
            mat_idx = mat_list.find(grid.mat_id)
            if mat_idx < 0:
                remove_idx.append(idx)
                continue
            if mat_list[mat_idx].users == 0:
                remove_idx.append(idx)
        remove_idx.reverse()
        for idx in remove_idx:
            grids.remove(idx)

        # Loop through available materials, checking if grids has
        # at least one entry with the name
        for mat in mat_list:
            if mat.users == 0:
                continue
            is_mat_valid = False
            for grid in grids:
                if grid.mat_id == mat.name:
                    is_mat_valid = True
                    break
            # No grid found for this material, add new one
            if is_mat_valid is False:
                grid_setting = grids.add()
                grid_setting.mat_id = mat.name
                grid_setting.is_main = True

        grids_count = len(grids)
        if curr_sel >= grids_count:
            context.object.sprytile_gridid = grids_count-1


class SprytileGridTranslate(bpy.types.Operator):
    bl_idname = "sprytile.translate_grid"
    bl_label = "Sprytile Translate on Grid"

    def modal(self, context, event):
        if self.exit:
            print('Finishing grid translate modal')
            op = context.active_operator
            if op is not None and op.bl_idname == 'TRANSFORM_OT_translate':
                pixel_unit = 1 / context.scene.sprytile_data.world_pixels
                translation = op.properties.value.copy()
                for i in range(3):
                    translation[i] = int(round(translation[i] / pixel_unit))
                    translation[i] *= pixel_unit
                offset = translation - op.properties.value
                bpy.ops.transform.translate(value=offset)
            context.window_manager.event_timer_remove(self.timer)
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'LEFTMOUSE'} and event.value == 'PRESS':
            self.exit = True

        return {'PASS_THROUGH'}

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        up_vec, right_vec, norm_vec = sprytile_modal.get_current_grid_vectors(context.scene)
        norm_vec = sprytile_modal.snap_vector_to_axis(norm_vec)
        axis_constraint = [
            abs(norm_vec.x) == 0,
            abs(norm_vec.y) == 0,
            abs(norm_vec.z) == 0
        ]

        bpy.ops.transform.translate(
            'INVOKE_REGION_WIN',
            constraint_axis=axis_constraint
        )

        self.exit = False

        win_mgr = context.window_manager
        self.timer = win_mgr.event_timer_add(0.1, context.window)
        win_mgr.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class SprytileWorkflowPanel(bpy.types.Panel):
    bl_label = "Workflow"
    bl_idname = "sprytile.panel_workflow"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Sprytile"

    @classmethod
    def poll(cls, context):
        if context.object and context.object.type == 'MESH':
            return context.object.mode == 'EDIT'

    def draw(self, context):
        layout = self.layout
        data = context.scene.sprytile_data

        row = layout.row(align=True)
        row.prop(data, "uv_flip_x", toggle=True)
        row.prop(data, "uv_flip_y", toggle=True)

        layout.prop(data, "mesh_rotate")

        row = layout.row(align=False)
        row.label("", icon="SNAP_ON")
        row.prop(data, "cursor_snap", expand=True)

        row = layout.row(align=False)
        row.label("", icon="CURSOR")
        row.prop(data, "cursor_flow", toggle=True)

        layout.prop(data, "world_pixels")


def register():
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)


if __name__ == '__main__':
    register()
