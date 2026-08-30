FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

annotation { "Feature Type Name" : "Mini2" }
export const mini2 = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Faces", "Filter" : EntityType.FACE && GeometryType.PLANE }
        definition.faces is Query;

        annotation { "Name" : "Size" }
        isLength(definition.size, LENGTH_BOUNDS);
    }
    {
        // 空實作：唯一與 minimal.fs 的差別是多了一個 Query 參數
    });
