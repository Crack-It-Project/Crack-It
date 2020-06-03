-- phpMyAdmin SQL Dump
-- version 4.6.6deb5
-- https://www.phpmyadmin.net/
--
-- Client :  localhost:3306
-- Généré le :  Lun 04 Mai 2020 à 16:43
-- Version du serveur :  10.3.22-MariaDB-0+deb10u1
-- Version de PHP :  7.3.14-1~deb10u1

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données :  `crack_it`
--

-- --------------------------------------------------------

--
-- Structure de la table `dict`
--

CREATE TABLE `dict` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `password` varchar(535) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `seen` int(11) NOT NULL DEFAULT 1,
  `date` date DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Structure de la table `hash`
--

CREATE TABLE `hash` (
  `str` varchar(255) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `algo` varchar(255) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `clear` varchar(535) CHARACTER SET utf8 COLLATE utf8_unicode_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Structure de la table `origin_dict`
--

CREATE TABLE `origin_dict` (
  `srckey` varchar(255) NOT NULL,
  `item` bigint(20) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Store from where an entry in dict has been pulled from';

-- --------------------------------------------------------

--
-- Structure de la table `source`
--

CREATE TABLE `source` (
  `idsource` bigint(20) UNSIGNED NOT NULL,
  `url` tinytext DEFAULT NULL,
  `module` varchar(45) DEFAULT NULL,
  `name` tinytext DEFAULT NULL,
  `sourceHint` varchar(255) DEFAULT NULL COMMENT 'Used by the modules to know when was the last time this soruce was checked (could be date but also hash etc...)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Contenu de la table `source`
--

INSERT INTO `source` (`idsource`, `url`, `module`, `name`, `sourceHint`) VALUES
#(2, 'https://github.com/danielmiessler/SecLists.git', 'git', NULL, NULL),
(3, 'https://scrape.pastebin.com/api_scraping.php?lang=email', 'pastebin', NULL, NULL),
(4, 'https://scrape.pastebin.com/api_scraping.php?lang=bash', 'pastebin', NULL, NULL);

--
-- Index pour les tables exportées
--

--
-- Index pour la table `dict`
--
ALTER TABLE `dict`
  ADD PRIMARY KEY (`password`),
  ADD UNIQUE KEY `password` (`password`),
  ADD UNIQUE KEY `id` (`id`);

--
-- Index pour la table `hash`
--
ALTER TABLE `hash`
  ADD PRIMARY KEY (`str`),
  ADD KEY `clear` (`clear`);

--
-- Index pour la table `origin_dict`
--
ALTER TABLE `origin_dict`
  ADD PRIMARY KEY (`srckey`,`item`),
  ADD KEY `orgin_dict-dict_FK` (`item`),
  ADD KEY `srckey` (`srckey`);

--
-- Index pour la table `source`
--
ALTER TABLE `source`
  ADD PRIMARY KEY (`idsource`);

--
-- AUTO_INCREMENT pour les tables exportées
--

--
-- AUTO_INCREMENT pour la table `dict`
--
ALTER TABLE `dict`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;
--
-- AUTO_INCREMENT pour la table `source`
--
ALTER TABLE `source`
  MODIFY `idsource` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;
--
-- Contraintes pour les tables exportées
--

--
-- Contraintes pour la table `hash`
--
ALTER TABLE `hash`
  ADD CONSTRAINT `hash_ibfk_1` FOREIGN KEY (`clear`) REFERENCES `dict` (`password`);

--
-- Contraintes pour la table `origin_dict`
--
ALTER TABLE `origin_dict`
  ADD CONSTRAINT `orgin_dict-dict_FK` FOREIGN KEY (`item`) REFERENCES `dict` (`id`);

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
