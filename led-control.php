<!DOCTYPE html>
<html>
<head>
<title>LED Control</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
<link rel="shortcut icon" href="/src/favicon.ico" type="image/vnd.microsoft.icon">
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"></script>
<style>
.container {
    background-color: #f2f2f2;
    padding: 5px 20px 15px 20px;
    border: 1px solid lightgrey;
    border-radius: 3px;
}
.btn {
    width: 100%;
	border-radius:5px;
	display:block;
	cursor:pointer;
	color:#ffffff;
	font-family:Arial;
	font-size:15px;
	padding:10px 36px;
	text-decoration:none;
    margin: 10px 0px;
}
.btn-light {
	background-color:#d22e25;
}
.btn-dark {
    background-color:#b23e35;
}
.btn-blue-light {
    background-color:#00b2ff;
}
.btn-blue-dark {
    background-color:#00a2d9;
}
.btn-grey {
    background-color:#8c8c8c;
}
.btn-light:active
.btn-dark:active {
	background-color:#eb675e;
}
.btn:active {
	position:relative;
	top:1px;
}


</style>
</head>
<body>
<h1 style="text-align: center;">LED Control</h1>

<!-- same thing but with a for loop -->
<?php 
    $messages = array("Bonjour !", "Merci", "Horloge", "Doublez-moi", "Tesla", "Désolé");
    $commands = array("bonjour.sh", "merci.sh", "clock.sh", "overtake.sh", "tesla.sh", "desole.sh");

    $useless_crap = array("Carre qui tourne");
    $useless_commands = array("carre.sh");

    ## if $_GET['run'] is set and is one of the commands, run the corresponding script
    if (isset($_GET['run']) && in_array($_GET['run'], $commands)) {
        $command = $_GET['run'];
        $pid = exec("/bin/bash /home/pi/src/$command &");
    }
?>
<div class="container">
    <!-- while i is less than the number of messages, display a button for each message -->
    <?php for ($i = 0; $i < count($messages); $i++) { ?>
        <!-- every other button is red -->
        <!-- on click, run the corresponding shell script -->
            <a class="btn btn-<?php if ($i%2==0) { ?>dark<?php } else { ?>light<?php } ?>" id="<?php echo $i; ?>" href="?run=<?php echo $commands[$i]; ?>">
                <?php echo $messages[$i]; ?>
            </a>
    <?php }
        for ($j = 0; $j < count($useless_crap); $j++) { ?>
        <!-- every other button is blue -->
        <!-- on click, run the corresponding shell script -->
            <a class="btn btn-<?php if ($j%2==0) { ?>blue-dark<?php } else { ?>blue-light<?php } ?>" id="<?php echo $j; ?>" href="?run=<?php echo $useless_commands[$j]; ?>">
                <?php echo $useless_crap[$j]; ?>
            </a>
    <?php } ?>

    <!-- RESET button -->
    <a class="btn btn-grey" href="?run=reset.sh">RESET</a>
</div>
</body>
</html>
