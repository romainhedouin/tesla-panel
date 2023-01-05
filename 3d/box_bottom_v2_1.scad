box_length=90;
box_width=59;
small_distance_between_holes=49;
box_height=30;
SD_side_grabber_length=15;
thickness=2;

// #translate([-2, 0, 27]) cube([1, 59, 1]);

//flat grabber
difference() {
    translate([-thickness, -thickness, -thickness])cube([box_length+SD_side_grabber_length, box_width+(thickness*2), thickness]);
    translate([84, 20, -5])cube([30, 16, 10]);
    translate([97, 6, -5]) cylinder(10, 1.8, 1.8);
}

difference () {
//grabber
    translate([-20-thickness, -thickness, -thickness]) cube([20, box_width+(thickness*2), thickness]);
    
    translate([-15, 6, -5]) cylinder(10, 1.8, 1.8);
}

// distance of 4 from right-most edge
// two sticks, close to closed side
translate([box_length - 5.6, 4, 0]) cylinder(26, 2.8/2, 2.8/2);
translate([box_length - 5.4, 53.4, 0]) cylinder(26, 2.8/2, 2.8/2);

// distance of 62 from right-most-edge
// two sticks, close to open side
translate([box_length - 63.8, 4, 0]) cylinder(26, 2.8/2, 2.8/2);
translate([box_length - 63.4, 53, 0]) cylinder(26, 2.8/2, 2.8/2);

// side support
translate([-thickness, -thickness, -thickness])cube([box_length + thickness, thickness, box_height]);
translate([84, box_width, -thickness])cube([5, thickness, box_height]);
translate([-thickness, box_width, -thickness])cube([20, thickness, box_height]);

difference() {
    translate([89, -thickness, -thickness]) cube([thickness, box_width+(2*thickness), box_height]);
    translate([88, 20, -10]) cube([thickness+2, 16, 50]);
}