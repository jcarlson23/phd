// -*- c-basic-offset: 8; -*-
#ifndef SCENE_H_
#define SCENE_H_

#include "./lights.h"
#include "./objects.h"

// A full scene, consisting of objects (spheres) and lighting (point
// lights).
class Scene {
public:
    const std::vector<const Object *> objects;
    const std::vector<const Light *> lights;

    // Constructor.
    inline Scene(const std::vector<const Object *> &_objects,
                 const std::vector<const Light *> &_lights)
            : objects(_objects), lights(_lights) {}

    inline ~Scene() {
        for (size_t i = 0; i < objects.size(); i++)
            delete objects[i];
        for (size_t i = 0; i < lights.size(); i++)
            delete lights[i];
    }
};

#endif  // SCENE_H_
