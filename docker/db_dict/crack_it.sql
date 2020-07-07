-- phpMyAdmin SQL Dump
-- version 5.0.2
-- https://www.phpmyadmin.net/
--
-- Host: db_dict:3306
-- Generation Time: Jul 03, 2020 at 09:04 AM
-- Server version: 10.4.13-MariaDB-1:10.4.13+maria~focal
-- PHP Version: 7.4.6

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `crack_it`
--

-- --------------------------------------------------------

--
-- Table structure for table `dict`
--

CREATE TABLE `dict` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `password` varchar(535) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `seen` int(11) NOT NULL DEFAULT 1,
  `date` date DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `hash`
--

CREATE TABLE `hash` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `str` varchar(255) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `algo` varchar(255) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `clear` bigint(20) UNSIGNED DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `origin_dict`
--

CREATE TABLE `origin_dict` (
  `srckey` varchar(255) NOT NULL,
  `item` bigint(20) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Store from where an entry in dict has been pulled from';

-- --------------------------------------------------------

--
-- Table structure for table `origin_hash`
--

CREATE TABLE `origin_hash` (
  `srckey` varchar(255) NOT NULL,
  `item` bigint(20) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

-- --------------------------------------------------------

--
-- Table structure for table `source`
--

CREATE TABLE `source` (
  `idsource` bigint(20) UNSIGNED NOT NULL,
  `url` tinytext DEFAULT NULL,
  `module` varchar(45) DEFAULT NULL,
  `name` tinytext DEFAULT NULL,
  `sourceHint` varchar(255) DEFAULT NULL COMMENT 'Used by the modules to know when was the last time this soruce was checked (could be date but also hash etc...)',
  `weight` int(255) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `source`
--

INSERT INTO `source` (`idsource`, `url`, `module`, `name`, `sourceHint`, `weight`) VALUES
(1, 'https://github.com/JL-intech/rockyou.git', 'git', NULL, NULL, 100),
(2, 'https://scrape.pastebin.com/api_scraping.php?lang=email', 'pastebin', NULL, '1593704504', 1),
(3, 'https://scrape.pastebin.com/api_scraping.php?lang=bash', 'pastebin', NULL, '1593766181', 1);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `dict`
--
ALTER TABLE `dict`
  ADD PRIMARY KEY (`password`),
  ADD UNIQUE KEY `password` (`password`),
  ADD UNIQUE KEY `id` (`id`);

--
-- Indexes for table `hash`
--
ALTER TABLE `hash`
  ADD PRIMARY KEY (`str`),
  ADD UNIQUE KEY `id` (`id`),
  ADD KEY `clear` (`clear`);

--
-- Indexes for table `origin_dict`
--
ALTER TABLE `origin_dict`
  ADD PRIMARY KEY (`srckey`,`item`),
  ADD KEY `orgin_dict-dict_FK` (`item`),
  ADD KEY `srckey` (`srckey`);

--
-- Indexes for table `origin_hash`
--
ALTER TABLE `origin_hash`
  ADD PRIMARY KEY (`srckey`),
  ADD KEY `origin_hash_hashId` (`item`);

--
-- Indexes for table `source`
--
ALTER TABLE `source`
  ADD PRIMARY KEY (`idsource`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `dict`
--
ALTER TABLE `dict`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `hash`
--
ALTER TABLE `hash`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `source`
--
ALTER TABLE `source`
  MODIFY `idsource` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `hash`
--
ALTER TABLE `hash`
  ADD CONSTRAINT `hash_ibfk_1` FOREIGN KEY (`clear`) REFERENCES `dict` (`id`);

--
-- Constraints for table `origin_dict`
--
ALTER TABLE `origin_dict`
  ADD CONSTRAINT `orgin_dict-dict_FK` FOREIGN KEY (`item`) REFERENCES `dict` (`id`);

--
-- Constraints for table `origin_hash`
--
ALTER TABLE `origin_hash`
  ADD CONSTRAINT `origin_hash_hashId` FOREIGN KEY (`item`) REFERENCES `hash` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
