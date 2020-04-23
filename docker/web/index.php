<?php
$host = 'db';
$db_name = 'crack_it';
$user = 'python';
$pass = 'pythonpython';
$connexion = 'mysql:host=' . $host . ';dbname='. $db_name . ';charset=utf8';

try {
    $strConnexion = $connexion ;
    $pdo = new PDO ($strConnexion,$user,$pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e){
    $msg = 'Erreur PDO dans ' . $e -> getMessage();
    die($msg);
}

$test = $pdo->prepare("SELECT * FROM dict") ;
$test->execute() ;
$test = $test->fetchAll() ;

var_dump($test);