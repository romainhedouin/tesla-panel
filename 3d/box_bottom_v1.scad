board_real_length=87;
board_real_width=56;
box_length=((board_real_length+3));
box_width=59;
small_distance_between_holes=49;
box_height=30;
thickness=1;

difference() {
    translate([-thickness, 0, -thickness])cube([box_length, box_width+thickness, thickness]);
    translate([84, 20, -5])cube([30, 16, 10]);
}

// distance of 4 from right-most edge
// two sticks, close to closed side
translate([box_length - 5, 4, 0]) cylinder(30, 2/2, 2/2);
translate([box_length - 5, 53, 0]) cylinder(30, 2/2, 2/2);

// distance of 62 from right-most-edge
// two sticks, close to open side
translate([box_length - 64, 4, 0]) cylinder(30, 2/2, 2/2);
translate([box_length - 64, 53, 0]) cylinder(30, 2/2, 2/2);

// side support
translate([-thickness, -thickness, -thickness])cube([box_length, thickness, box_height]);
translate([-thickness, box_width, -thickness])cube([30, thickness, box_height]);
translate([85, box_width, -thickness])cube([5, thickness, box_height]);

difference() {
    translate([89, -thickness, -thickness])cube([thickness, box_width+(2*thickness), box_height]);
    translate([88, 20, -10])cube([thickness+2, 16, 50]);
}