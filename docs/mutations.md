# Mutations

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

Mutations are conversions which update the data in-place. Here is the list of
supported mutations:

 * `c.Mut.set_item(name, value)` - `d[name] = value` but as conversions
 * `c.Mut.set_attr(name, value)` - `setattr(obj, name, value)`
 * `c.Mut.del_item(index)` - `d.pop(index)`
 * `c.Mut.del_attr(index)` - `delattr(obj, index)`
 * `c.Mut.custom(any_conversion)`

and they cannot be used outside of the below methods.


## c.iter_mut

`c.iter_mut(*mutations)` mutates each element of a sequence and returns an
iterator of mutated objects.

{!examples-md/api__iter_mut.md!}

## c.tap

`c.tap(*mutations)` and `tap` conversion method mutate a single object.

{!examples-md/api__tap.md!}
