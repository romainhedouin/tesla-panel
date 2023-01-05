thickness=2;
box_length=90;
box_width=59 + (thickness * 2 * 2);

// #translate([thickness*2, -2, 0]) cube([59, 1, 1]);

cube([box_width, 28, thickness]);
translate([0, 0, 1]) cube([thickness, 30-thickness, thickness*3]);
translate([thickness*2, 0, 1]) cube([thickness, 30-thickness, thickness*3]);

translate([box_width-thickness, 0, 1]) cube([thickness, 28, thickness*3]);
translate([box_width-(thickness*3), 0, 1]) cube([thickness, 28, thickness*3]);

translate([box_width - (thickness * 3) - 23, 17, thickness]) cube([23+thickness, 11, 10]);
