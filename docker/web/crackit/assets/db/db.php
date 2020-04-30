<?php
try{//Tentative de connexion à la BDD via PDO
	$db = new PDO('mysql:host=localhost;dbname=crackit;charset=utf8','root', '');
	$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
	$db->exec("SET CHARACTER SET utf8");
	
	}catch (PDOException $e) {//erreur de connexion retourne un message avec l'erreur
    $msg = 'ERREUR PDO dans' . $e ->getMessage();
    die($msg);
}

?>