# Mutations

**Please, make sure you've covered [Reference / Basics](./basics.md) first.**


Mutations are conversions which update the data in-place. Here is the list of
supported mutations:

!!! warning "Experimental feature"
    `of_` parameter was added on Jun 7, 2024 and may be stabilized ~ in half a
    year.

| expected code | mutation |
|:--------------|:---------|
| `d[name] = value` |`c.Mut.set_item(name, value)`
| `d[1][2][name] = value` |`c.Mut.set_item(name, value, of_=c.item(1,2))`
| `setattr(obj, name, value)` |`c.Mut.set_attr(name, value)`
| `setattr(obj.a, name, value)` |`c.Mut.set_attr(name, value, of_=c.attr("a"))`
| `d.pop(index)` |`c.Mut.del_item(index)`
| `d.pop(index, None)` |`c.Mut.del_item(index, if_exists=True)`
| `d[1][2].pop(index)` |`c.Mut.del_item(index, of_=c.item(1,2))`
| `delattr(obj, index)` |`c.Mut.del_attr(index)`
| same, but if attr exists |`c.Mut.del_attr(index, if_exists=True)`
| `delattr(obj.a.b, index)` |`c.Mut.del_attr(index, of_=c.attr("a", "b"))`
| run a custom conversion |`c.Mut.custom(any_conversion)`

and they cannot be used outside of the below methods.


## c.iter_mut

`c.iter_mut(*mutations)` mutates each element of a sequence and returns an
iterator of mutated objects.

{!examples-md/api__iter_mut.md!}

## c.tap

`c.tap(*mutations)` and `tap` conversion method mutate a single object.

{!examples-md/api__tap.md!}
