FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

annotation { "Feature Type Name" : "Mini" }
export const mini = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Size" }
        isLength(definition.size, LENGTH_BOUNDS);
    }
    {
        // 空實作：只驗證 harness 能不能找到並編譯這個特徵
    });
