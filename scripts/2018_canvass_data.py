#!/usr/bin/env python3
"""Transcribed data from the SD 2018 General Election State Canvass PDF
(scanned; read page-by-page from rendered images) and the recount certificate PDF.

Each contest: (office, district, [(candidate, party), ...], rows, totals)
  rows: (county, [votes per candidate]) in printed order
  totals: printed Total row (used to validate the per-column county sums)

Recount values (from the recount certificate PDF) are already applied to
State Senate District 12 and State House Districts 09, 25, 27.
"""

# (office, district, candidates, rows, totals)
US_HOUSE = ("U.S. House", "1",
    [("George D. Hendrickson", "LIB"), ('Dustin "Dusty" Johnson', "REP"),
     ("Tim Bjorkman", "DEM"), ("Ron Wieczorek", "IND")],
    [
        ("Aurora", [11, 728, 443, 78]), ("Beadle", [74, 3825, 1983, 151]),
        ("Bennett", [14, 604, 438, 21]), ("Bon Homme", [35, 1674, 940, 62]),
        ("Brookings", [196, 6418, 4717, 322]), ("Brown", [156, 8346, 5482, 255]),
        ("Brule", [26, 1231, 814, 52]), ("Buffalo", [7, 172, 330, 21]),
        ("Butte", [59, 2799, 836, 90]), ("Campbell", [7, 601, 108, 9]),
        ("Charles Mix", [35, 2085, 1319, 91]), ("Clark", [13, 1150, 452, 34]),
        ("Clay", [68, 1906, 2567, 66]), ("Codington", [125, 7129, 3144, 160]),
        ("Corson", [15, 484, 557, 29]), ("Custer", [62, 2944, 1273, 99]),
        ("Davison", [61, 4807, 2160, 222]), ("Day", [36, 1541, 1072, 68]),
        ("Deuel", [27, 1272, 624, 46]), ("Dewey", [27, 623, 1084, 59]),
        ("Douglas", [13, 1162, 265, 54]), ("Edmunds", [14, 1147, 488, 36]),
        ("Fall River", [69, 2149, 882, 83]), ("Faulk", [15, 780, 255, 15]),
        ("Grant", [60, 2121, 945, 63]), ("Gregory", [13, 1484, 586, 39]),
        ("Haakon", [13, 796, 117, 14]), ("Hamlin", [27, 1939, 695, 47]),
        ("Hand", [15, 1171, 429, 34]), ("Hanson", [7, 1022, 536, 31]),
        ("Harding", [9, 568, 94, 11]), ("Hughes", [85, 5366, 2332, 175]),
        ("Hutchinson", [25, 2281, 883, 81]), ("Hyde", [8, 462, 164, 19]),
        ("Jackson", [7, 575, 370, 20]), ("Jerauld", [8, 567, 312, 20]),
        ("Jones", [11, 420, 94, 17]), ("Kingsbury", [26, 1507, 855, 44]),
        ("Lake", [42, 3110, 1925, 93]), ("Lawrence", [216, 6868, 3489, 271]),
        ("Lincoln", [339, 15049, 8266, 351]), ("Lyman", [21, 830, 500, 32]),
        ("Marshall", [28, 1024, 860, 33]), ("McCook", [20, 1373, 1047, 44]),
        ("McPherson", [14, 798, 216, 19]), ("Meade", [205, 7160, 2508, 269]),
        ("Mellette", [22, 358, 303, 16]), ("Miner", [13, 642, 413, 31]),
        ("Minnehaha", [1243, 38017, 29365, 1349]),
        ("Moody", [41, 1622, 1090, 72]), ("Oglala Lakota", [48, 336, 2473, 104]),
        ("Pennington", [728, 25433, 14092, 1093]),
        ("Perkins", [21, 1064, 224, 24]), ("Potter", [13, 923, 248, 12]),
        ("Roberts", [34, 1915, 1664, 71]), ("Sanborn", [11, 678, 292, 36]),
        ("Spink", [26, 1736, 958, 60]), ("Stanley", [15, 1042, 377, 45]),
        ("Sully", [4, 613, 182, 10]), ("Todd", [30, 506, 1598, 61]),
        ("Tripp", [24, 1814, 556, 48]), ("Turner", [47, 2467, 1262, 70]),
        ("Union", [86, 4282, 2152, 99]), ("Walworth", [28, 1648, 528, 40]),
        ("Yankton", [103, 5191, 3383, 205]), ("Ziebach", [13, 340, 417, 27]),
    ],
    [4914, 202695, 121033, 7323])

GOVERNOR = ("Governor", "",
    [("Kurt Evans", "LIB"), ("Kristi Noem", "REP"), ("Billie Sutton", "DEM")],
    [
        ("Aurora", [29, 644, 607]), ("Beadle", [94, 3182, 2832]),
        ("Bennett", [26, 553, 523]), ("Bon Homme", [36, 1303, 1408]),
        ("Brookings", [183, 5225, 6372]), ("Brown", [206, 6821, 7338]),
        ("Brule", [36, 1103, 991]), ("Buffalo", [7, 138, 403]),
        ("Butte", [69, 2505, 1234]), ("Campbell", [9, 550, 173]),
        ("Charles Mix", [38, 1661, 1853]), ("Clark", [17, 879, 768]),
        ("Clay", [53, 1552, 3039]), ("Codington", [131, 5865, 4697]),
        ("Corson", [17, 426, 667]), ("Custer", [73, 2789, 1547]),
        ("Davison", [97, 3779, 3398]), ("Day", [39, 1207, 1531]),
        ("Deuel", [43, 1053, 893]), ("Dewey", [18, 393, 1430]),
        ("Douglas", [13, 1120, 363]), ("Edmunds", [19, 1018, 671]),
        ("Fall River", [68, 2059, 1065]), ("Faulk", [13, 674, 388]),
        ("Grant", [52, 1780, 1388]), ("Gregory", [17, 1107, 1029]),
        ("Haakon", [15, 734, 196]), ("Hamlin", [29, 1764, 923]),
        ("Hand", [29, 950, 683]), ("Hanson", [18, 945, 647]),
        ("Harding", [7, 505, 174]), ("Hughes", [114, 3749, 4144]),
        ("Hutchinson", [28, 2082, 1180]), ("Hyde", [5, 407, 248]),
        ("Jackson", [20, 513, 454]), ("Jerauld", [12, 478, 433]),
        ("Jones", [12, 361, 173]), ("Kingsbury", [41, 1303, 1111]),
        ("Lake", [55, 2483, 2669]), ("Lawrence", [239, 5984, 4675]),
        ("Lincoln", [203, 12894, 11109]), ("Lyman", [27, 691, 682]),
        ("Marshall", [31, 853, 1093]), ("McCook", [39, 1375, 1083]),
        ("McPherson", [16, 729, 309]), ("Meade", [256, 6413, 3559]),
        ("Mellette", [17, 299, 395]), ("Miner", [12, 523, 570]),
        ("Minnehaha", [876, 32355, 37450]), ("Moody", [44, 1340, 1469]),
        ("Oglala Lakota", [44, 214, 2778]), ("Pennington", [738, 22944, 17988]),
        ("Perkins", [23, 953, 368]), ("Potter", [15, 821, 373]),
        ("Roberts", [40, 1643, 2062]), ("Sanborn", [16, 593, 419]),
        ("Spink", [37, 1376, 1394]), ("Stanley", [21, 762, 704]),
        ("Sully", [16, 500, 296]), ("Todd", [20, 390, 1831]),
        ("Tripp", [36, 1430, 1023]), ("Turner", [39, 2272, 1556]),
        ("Union", [73, 4068, 2544]), ("Walworth", [39, 1468, 752]),
        ("Yankton", [134, 4121, 4757]), ("Ziebach", [9, 241, 572]),
    ],
    [4848, 172912, 161454])

SOS = ("Secretary of State", "",
    [("Steve Barnett", "REP"), ("Alexandra Frederick", "DEM")],
    [
        ("Aurora", [830, 391]), ("Beadle", [3425, 2181]), ("Bennett", [608, 446]),
        ("Bon Homme", [1781, 797]), ("Brookings", [6744, 4469]),
        ("Brown", [9503, 4468]), ("Brule", [1439, 580]), ("Buffalo", [165, 354]),
        ("Butte", [2908, 779]), ("Campbell", [633, 81]),
        ("Charles Mix", [2218, 1238]), ("Clark", [1127, 460]),
        ("Clay", [2017, 2377]), ("Codington", [6975, 3091]),
        ("Corson", [474, 612]), ("Custer", [3102, 1185]),
        ("Davison", [4869, 2029]), ("Day", [1586, 1023]), ("Deuel", [1300, 584]),
        ("Dewey", [642, 1130]), ("Douglas", [1266, 172]), ("Edmunds", [1258, 372]),
        ("Fall River", [2241, 857]), ("Faulk", [837, 201]),
        ("Grant", [2134, 900]), ("Gregory", [1518, 505]), ("Haakon", [832, 94]),
        ("Hamlin", [2009, 581]), ("Hand", [1228, 367]), ("Hanson", [1119, 399]),
        ("Harding", [612, 56]), ("Hughes", [5860, 1963]),
        ("Hutchinson", [2490, 640]), ("Hyde", [496, 151]), ("Jackson", [603, 352]),
        ("Jerauld", [599, 269]), ("Jones", [439, 86]), ("Kingsbury", [1618, 714]),
        ("Lake", [3331, 1605]), ("Lawrence", [6992, 3552]),
        ("Lincoln", [15683, 7368]), ("Lyman", [915, 437]),
        ("Marshall", [1069, 794]), ("McCook", [1693, 666]),
        ("McPherson", [876, 156]), ("Meade", [7276, 2534]),
        ("Mellette", [383, 302]), ("Miner", [664, 338]),
        ("Minnehaha", [39634, 27329]), ("Moody", [1633, 1067]),
        ("Oglala Lakota", [276, 2692]), ("Pennington", [25954, 14175]),
        ("Perkins", [1057, 217]), ("Potter", [992, 168]),
        ("Roberts", [1879, 1654]), ("Sanborn", [738, 233]),
        ("Spink", [1844, 864]), ("Stanley", [1126, 329]), ("Sully", [656, 141]),
        ("Todd", [488, 1700]), ("Tripp", [1860, 531]), ("Turner", [2730, 946]),
        ("Union", [4444, 2040]), ("Walworth", [1752, 435]),
        ("Yankton", [5276, 3140]), ("Ziebach", [338, 440]),
    ],
    [211064, 112807])

AG = ("Attorney General", "",
    [("Jason Ravnsborg", "REP"), ("Randy Seiler", "DEM")],
    [
        ("Aurora", [702, 521]), ("Beadle", [3042, 2714]), ("Bennett", [552, 500]),
        ("Bon Homme", [1504, 1111]), ("Brookings", [5698, 5521]),
        ("Brown", [7186, 6609]), ("Brule", [1238, 783]), ("Buffalo", [157, 367]),
        ("Butte", [2665, 1024]), ("Campbell", [475, 252]),
        ("Charles Mix", [1839, 1619]), ("Clark", [961, 623]),
        ("Clay", [1675, 2776]), ("Codington", [6013, 4085]),
        ("Corson", [419, 677]), ("Custer", [2892, 1412]),
        ("Davison", [3925, 3003]), ("Day", [1258, 1342]), ("Deuel", [1102, 787]),
        ("Dewey", [490, 1292]), ("Douglas", [1116, 327]), ("Edmunds", [1016, 607]),
        ("Fall River", [2069, 1058]), ("Faulk", [759, 267]),
        ("Grant", [1890, 1156]), ("Gregory", [1239, 777]), ("Haakon", [742, 176]),
        ("Hamlin", [1809, 781]), ("Hand", [1024, 565]), ("Hanson", [979, 557]),
        ("Harding", [550, 110]), ("Hughes", [3517, 4304]),
        ("Hutchinson", [2085, 1079]), ("Hyde", [412, 231]), ("Jackson", [531, 425]),
        ("Jerauld", [475, 392]), ("Jones", [390, 130]), ("Kingsbury", [1394, 937]),
        ("Lake", [2733, 2242]), ("Lawrence", [6260, 4275]),
        ("Lincoln", [13025, 10071]), ("Lyman", [780, 550]),
        ("Marshall", [862, 1006]), ("McCook", [1420, 947]),
        ("McPherson", [771, 251]), ("Meade", [6656, 3168]),
        ("Mellette", [346, 333]), ("Miner", [569, 457]),
        ("Minnehaha", [32899, 34203]), ("Moody", [1398, 1326]),
        ("Oglala Lakota", [239, 2726]), ("Pennington", [23559, 16635]),
        ("Perkins", [945, 338]), ("Potter", [820, 327]),
        ("Roberts", [1657, 1905]), ("Sanborn", [606, 373]),
        ("Spink", [1476, 1224]), ("Stanley", [628, 838]), ("Sully", [504, 297]),
        ("Todd", [462, 1679]), ("Tripp", [1604, 798]), ("Turner", [2348, 1325]),
        ("Union", [4144, 2326]), ("Walworth", [1380, 819]),
        ("Yankton", [4921, 3694]), ("Ziebach", [269, 528]),
    ],
    [179071, 145558])

AUDITOR = ("State Auditor", "",
    [("Rich Sattgast", "REP"), ("Tom Cool", "DEM")],
    [
        ("Aurora", [775, 400]), ("Beadle", [4057, 1711]), ("Bennett", [581, 466]),
        ("Bon Homme", [1658, 846]), ("Brookings", [6384, 4442]),
        ("Brown", [8186, 5196]), ("Brule", [1380, 603]), ("Buffalo", [160, 346]),
        ("Butte", [2824, 804]), ("Campbell", [608, 90]),
        ("Charles Mix", [1929, 1429]), ("Clark", [1095, 440]),
        ("Clay", [1919, 2382]), ("Codington", [6631, 3076]),
        ("Corson", [458, 613]), ("Custer", [3042, 1176]),
        ("Davison", [4621, 2095]), ("Day", [1463, 1024]), ("Deuel", [1230, 600]),
        ("Dewey", [597, 1149]), ("Douglas", [1207, 207]), ("Edmunds", [1124, 435]),
        ("Fall River", [2185, 871]), ("Faulk", [783, 228]),
        ("Grant", [2036, 904]), ("Gregory", [1406, 579]), ("Haakon", [792, 108]),
        ("Hamlin", [1945, 583]), ("Hand", [1201, 369]), ("Hanson", [1039, 430]),
        ("Harding", [585, 66]), ("Hughes", [5712, 1999]),
        ("Hutchinson", [2314, 701]), ("Hyde", [490, 149]), ("Jackson", [568, 363]),
        ("Jerauld", [587, 264]), ("Jones", [428, 83]), ("Kingsbury", [1572, 705]),
        ("Lake", [3185, 1635]), ("Lawrence", [6990, 3377]),
        ("Lincoln", [15149, 7370]), ("Lyman", [873, 433]),
        ("Marshall", [990, 810]), ("McCook", [1607, 675]),
        ("McPherson", [831, 176]), ("Meade", [7054, 2482]),
        ("Mellette", [365, 299]), ("Miner", [640, 328]),
        ("Minnehaha", [37587, 27552]), ("Moody", [1552, 1069]),
        ("Oglala Lakota", [247, 2678]), ("Pennington", [25454, 13738]),
        ("Perkins", [1017, 226]), ("Potter", [945, 185]),
        ("Roberts", [1791, 1629]), ("Sanborn", [711, 233]),
        ("Spink", [1736, 908]), ("Stanley", [1094, 337]), ("Sully", [646, 139]),
        ("Todd", [459, 1660]), ("Tripp", [1806, 530]), ("Turner", [2558, 973]),
        ("Union", [4314, 2055]), ("Walworth", [1625, 506]),
        ("Yankton", [4926, 3247]), ("Ziebach", [331, 446]),
    ],
    [202055, 113628])

TREASURER = ("State Treasurer", "",
    [("Josh Haeder", "REP"), ("Aaron Matson", "DEM")],
    [
        ("Aurora", [716, 437]), ("Beadle", [4449, 1517]), ("Bennett", [563, 475]),
        ("Bon Homme", [1581, 879]), ("Brookings", [6159, 4580]),
        ("Brown", [7862, 5444]), ("Brule", [1262, 672]), ("Buffalo", [150, 356]),
        ("Butte", [2783, 816]), ("Campbell", [597, 98]),
        ("Charles Mix", [1934, 1377]), ("Clark", [1041, 480]),
        ("Clay", [1836, 2418]), ("Codington", [6307, 3312]),
        ("Corson", [462, 598]), ("Custer", [3002, 1196]),
        ("Davison", [4342, 2265]), ("Day", [1348, 1109]), ("Deuel", [1177, 641]),
        ("Dewey", [567, 1164]), ("Douglas", [1135, 259]), ("Edmunds", [1100, 451]),
        ("Fall River", [2166, 876]), ("Faulk", [762, 225]),
        ("Grant", [1941, 987]), ("Gregory", [1330, 624]), ("Haakon", [786, 110]),
        ("Hamlin", [1889, 612]), ("Hand", [1243, 340]), ("Hanson", [1015, 446]),
        ("Harding", [575, 75]), ("Hughes", [5221, 2275]),
        ("Hutchinson", [2234, 782]), ("Hyde", [467, 156]), ("Jackson", [566, 367]),
        ("Jerauld", [595, 266]), ("Jones", [414, 91]), ("Kingsbury", [1538, 722]),
        ("Lake", [2942, 1806]), ("Lawrence", [6766, 3554]),
        ("Lincoln", [14379, 7834]), ("Lyman", [824, 459]),
        ("Marshall", [904, 874]), ("McCook", [1492, 754]),
        ("McPherson", [813, 185]), ("Meade", [7006, 2526]),
        ("Mellette", [361, 302]), ("Miner", [587, 354]),
        ("Minnehaha", [35719, 28315]), ("Moody", [1448, 1163]),
        ("Oglala Lakota", [247, 2679]), ("Pennington", [25230, 13891]),
        ("Perkins", [1010, 235]), ("Potter", [911, 196]),
        ("Roberts", [1689, 1726]), ("Sanborn", [688, 260]),
        ("Spink", [1615, 1007]), ("Stanley", [1018, 373]), ("Sully", [590, 175]),
        ("Todd", [456, 1664]), ("Tripp", [1720, 590]), ("Turner", [2450, 1058]),
        ("Union", [4311, 2066]), ("Walworth", [1638, 492]),
        ("Yankton", [4780, 3265]), ("Ziebach", [310, 462]),
    ],
    [195019, 117763])

LANDS = ("Commissioner of School and Public Lands", "",
    [("Ryan Brunner", "REP"), ("Woody Houser", "DEM")],
    [
        ("Aurora", [734, 412]), ("Beadle", [3548, 1984]), ("Bennett", [568, 467]),
        ("Bon Homme", [1606, 838]), ("Brookings", [6577, 4257]),
        ("Brown", [7721, 5415]), ("Brule", [1286, 630]), ("Buffalo", [148, 358]),
        ("Butte", [2953, 742]), ("Campbell", [597, 96]),
        ("Charles Mix", [2019, 1278]), ("Clark", [1005, 486]),
        ("Clay", [1906, 2379]), ("Codington", [6213, 3182]),
        ("Corson", [470, 596]), ("Custer", [3009, 1196]),
        ("Davison", [4304, 2221]), ("Day", [1345, 1095]), ("Deuel", [1166, 611]),
        ("Dewey", [578, 1153]), ("Douglas", [1186, 201]), ("Edmunds", [1078, 457]),
        ("Fall River", [2143, 901]), ("Faulk", [760, 224]),
        ("Grant", [1945, 958]), ("Gregory", [1339, 601]), ("Haakon", [804, 92]),
        ("Hamlin", [1865, 608]), ("Hand", [1096, 436]), ("Hanson", [997, 445]),
        ("Harding", [606, 63]), ("Hughes", [5304, 2158]),
        ("Hutchinson", [2253, 731]), ("Hyde", [456, 172]), ("Jackson", [580, 363]),
        ("Jerauld", [522, 310]), ("Jones", [414, 86]), ("Kingsbury", [1507, 717]),
        ("Lake", [2953, 1753]), ("Lawrence", [6787, 3526]),
        ("Lincoln", [14148, 7838]), ("Lyman", [836, 448]),
        ("Marshall", [940, 825]), ("McCook", [1509, 714]),
        ("McPherson", [810, 190]), ("Meade", [7223, 2450]),
        ("Mellette", [351, 305]), ("Miner", [594, 349]),
        ("Minnehaha", [35115, 28071]), ("Moody", [1485, 1119]),
        ("Oglala Lakota", [250, 2688]), ("Pennington", [24812, 13950]),
        ("Perkins", [1021, 239]), ("Potter", [907, 194]),
        ("Roberts", [1712, 1689]), ("Sanborn", [649, 253]),
        ("Spink", [1577, 1018]), ("Stanley", [1014, 369]), ("Sully", [595, 166]),
        ("Todd", [460, 1662]), ("Tripp", [1714, 576]), ("Turner", [2414, 1120]),
        ("Union", [4330, 2060]), ("Walworth", [1609, 503]),
        ("Yankton", [4695, 3347]), ("Ziebach", [316, 445]),
    ],
    [193434, 116786])

PUC = ("Public Utilities Commissioner", "",
    [("Kristie Fiegen", "REP"), ("Wayne Frederick", "DEM")],
    [
        ("Aurora", [807, 370]), ("Beadle", [3858, 1850]), ("Bennett", [551, 478]),
        ("Bon Homme", [1683, 799]), ("Brookings", [6852, 4120]),
        ("Brown", [8302, 5129]), ("Brule", [1387, 573]), ("Buffalo", [167, 348]),
        ("Butte", [2764, 807]), ("Campbell", [603, 90]),
        ("Charles Mix", [2095, 1206]), ("Clark", [1029, 496]),
        ("Clay", [2037, 2247]), ("Codington", [6685, 3051]),
        ("Corson", [464, 601]), ("Custer", [2994, 1157]),
        ("Davison", [4720, 2006]), ("Day", [1385, 1070]), ("Deuel", [1252, 595]),
        ("Dewey", [580, 1144]), ("Douglas", [1210, 189]), ("Edmunds", [1135, 416]),
        ("Fall River", [2143, 871]), ("Faulk", [775, 208]),
        ("Grant", [2037, 919]), ("Gregory", [1382, 553]), ("Haakon", [788, 105]),
        ("Hamlin", [1918, 599]), ("Hand", [1163, 380]), ("Hanson", [1078, 395]),
        ("Harding", [584, 72]), ("Hughes", [5433, 2090]),
        ("Hutchinson", [2434, 620]), ("Hyde", [477, 149]), ("Jackson", [574, 356]),
        ("Jerauld", [570, 277]), ("Jones", [424, 85]), ("Kingsbury", [1540, 731]),
        ("Lake", [3467, 1420]), ("Lawrence", [6827, 3433]),
        ("Lincoln", [15846, 6724]), ("Lyman", [865, 429]),
        ("Marshall", [938, 847]), ("McCook", [1670, 626]),
        ("McPherson", [816, 177]), ("Meade", [7120, 2461]),
        ("Mellette", [343, 336]), ("Miner", [691, 306]),
        ("Minnehaha", [40484, 24988]), ("Moody", [1671, 999]),
        ("Oglala Lakota", [266, 2669]), ("Pennington", [25374, 13575]),
        ("Perkins", [1003, 233]), ("Potter", [909, 192]),
        ("Roberts", [1727, 1681]), ("Sanborn", [716, 227]),
        ("Spink", [1705, 930]), ("Stanley", [1027, 370]), ("Sully", [639, 108]),
        ("Todd", [433, 1751]), ("Tripp", [1760, 582]), ("Turner", [2792, 846]),
        ("Union", [4408, 1932]), ("Walworth", [1646, 476]),
        ("Yankton", [5082, 3015]), ("Ziebach", [331, 440]),
    ],
    [206436, 108925])

# --- State Senate (post-recount values for District 12) ---
SENATE_1 = (
    ("State Senate", "1", [("Susan M. Wismer", "DEM")],
     [("Brown", [843]), ("Day", [1566]), ("Marshall", [1276]), ("Roberts", [2201])],
     [5886]))
SENATE_2 = (
    ("State Senate", "2", [("Brock L. Greenfield", "REP"), ("Paul Register", "DEM")],
     [("Brown", [1908, 1257]), ("Clark", [1107, 487]), ("Hamlin", [1998, 635]),
      ("Spink", [1561, 828])],
     [6574, 3207]))
SENATE_3 = (
    ("State Senate", "3", [("Al Novstrup", "REP"), ("Cory Allen Heidelberger", "DEM")],
     [("Brown", [5338, 3787])],
     [5338, 3787]))
SENATE_4 = (
    ("State Senate", "4", [("John Wiik", "REP"), ("Dennis Evenson", "DEM")],
     [("Brookings", [2351, 1195]), ("Codington", [982, 446]),
      ("Deuel", [1075, 870]), ("Grant", [2092, 1014])],
     [6500, 3525]))
SENATE_5 = (
    ("State Senate", "5", [("Lee Schoenbeck", "REP")],
     [("Codington", [6358])],
     [6358]))
SENATE_6 = (
    ("State Senate", "6", [("Ernie Otten", "REP"), ("Teresa Ann Robbins", "DEM")],
     [("Lincoln", [6945, 3725])],
     [6945, 3725]))
SENATE_7 = (
    ("State Senate", "7", [("V.J. Smith", "REP"), ("Mary J. Perpich", "IND")],
     [("Brookings", [4628, 2940])],
     [4628, 2940]))
SENATE_8 = (
    ("State Senate", "8", [("Jordan Youngberg", "REP"), ("Scott Parsley", "DEM")],
     [("Lake", [2801, 2355]), ("Miner", [585, 494]), ("Moody", [1418, 1367]),
      ("Sanborn", [713, 265])],
     [5517, 4481]))
SENATE_9 = (
    ("State Senate", "9", [("Wayne H. Steinhauer", "REP"), ("Laura Swier Kotelman", "DEM")],
     [("Minnehaha", [4759, 3640])],
     [4759, 3640]))
SENATE_10 = (
    ("State Senate", "10", [("Margaret Sutton", "REP"), ("Rachel Wilson", "DEM")],
     [("Minnehaha", [5240, 3558])],
     [5240, 3558]))
SENATE_11 = (
    ("State Senate", "11", [("Jim Stalzer", "REP"), ("Kevin Elsing", "DEM")],
     [("Minnehaha", [6190, 4058])],
     [6190, 4058]))
SENATE_12 = (
    ("State Senate", "12", [("R. Blake Curd", "REP"), ("Kasey Olivier", "DEM")],
     [("Lincoln", [2214, 1851]), ("Minnehaha", [2655, 2994])],
     [4869, 4845]))
SENATE_13 = (
    ("State Senate", "13", [("Jack Kolbeck", "REP"), ("Melissa Hiatt", "DEM")],
     [("Lincoln", [3093, 1682]), ("Minnehaha", [3072, 3533])],
     [6165, 5215]))
SENATE_14 = (
    ("State Senate", "14", [("Deb Soholt", "REP"), ("Justyn Hauck", "DEM")],
     [("Minnehaha", [6531, 4268])],
     [6531, 4268]))
SENATE_15 = (
    ("State Senate", "15", [("Reynold F. Nesiba", "DEM")],
     [("Minnehaha", [3258])],
     [3258]))
SENATE_16 = (
    ("State Senate", "16", [("Jim Bolin", "REP"), ("Elizabeth Merrigan", "DEM")],
     [("Lincoln", [2460, 965]), ("Union", [4355, 2166])],
     [6815, 3131]))
SENATE_17 = (
    ("State Senate", "17", [("Arthur Rusch", "REP"), ("Howard Grinager", "DEM")],
     [("Clay", [2534, 1949]), ("Turner", [2419, 1196])],
     [4953, 3145]))
SENATE_18 = (
    ("State Senate", "18", [("Roger Meyer", "REP"), ("Craig Kennedy", "DEM")],
     [("Yankton", [4061, 4518])],
     [4061, 4518]))
SENATE_19 = (
    ("State Senate", "19", [("Stace Nelson", "REP"), ("Ardon Wek", "DEM")],
     [("Bon Homme", [978, 598]), ("Douglas", [1236, 214]), ("Hanson", [1294, 286]),
      ("Hutchinson", [2228, 944]), ("McCook", [1795, 600])],
     [7531, 2642]))
SENATE_20 = (
    ("State Senate", "20", [("Joshua Klumb", "REP"), ("Dan Miller", "DEM")],
     [("Aurora", [913, 319]), ("Davison", [5100, 1917]), ("Jerauld", [593, 271])],
     [6606, 2507]))
SENATE_21 = (
    ("State Senate", "21", [("Rocky Dale Blare", "REP"), ("Julie Bartling", "DEM")],
     [("Bon Homme", [599, 427]), ("Charles Mix", [1548, 1910]),
      ("Gregory", [1066, 1051]), ("Tripp", [1705, 696])],
     [4918, 4084]))
SENATE_22 = (
    ("State Senate", "22", [("James White", "REP"), ("Eric Bliss", "DEM")],
     [("Beadle", [4342, 1559]), ("Kingsbury", [1591, 675])],
     [5933, 2234]))
SENATE_23 = (
    ("State Senate", "23", [("Justin R. Cronin", "REP"), ("Joe Yracheta", "DEM")],
     [("Campbell", [639, 75]), ("Edmunds", [1223, 347]), ("Faulk", [860, 161]),
      ("Hand", [1231, 322]), ("McPherson", [869, 146]), ("Potter", [1042, 144]),
      ("Spink", [205, 84]), ("Walworth", [1800, 382])],
     [7869, 1661]))
SENATE_24 = (
    ("State Senate", "24", [("Jeff Monroe", "REP"), ("Amanda Bachmann", "DEM")],
     [("Hughes", [4929, 2729]), ("Hyde", [462, 175]), ("Stanley", [985, 443]),
      ("Sully", [613, 172])],
     [6989, 3519]))
SENATE_25 = (
    ("State Senate", "25", [("Kris K. Langer", "REP"), ("Brian Wirth", "IND"),
                            ("Peter Klebanoff", "IND")],
     [("Minnehaha", [6583, 1931, 1125])],
     [6583, 1931, 1125]))
SENATE_26 = (
    ("State Senate", "26", [("Joel Koskan", "REP"), ("Troy Heinert", "DEM")],
     [("Brule", [1258, 774]), ("Buffalo", [149, 369]), ("Jones", [394, 135]),
      ("Lyman", [830, 527]), ("Mellette", [339, 357]), ("Todd", [480, 1734])],
     [3450, 3896]))
SENATE_27 = (
    ("State Senate", "27", [("Bill Hines", "REP"), ("Red Dawn Foster", "DEM")],
     [("Bennett", [658, 434]), ("Haakon", [833, 75]), ("Jackson", [609, 353]),
      ("Oglala Lakota", [219, 2780]), ("Pennington", [279, 31])],
     [2598, 3673]))
SENATE_28 = (
    ("State Senate", "28", [("Ryan M. Maher", "REP"), ("Alli Moran", "DEM")],
     [("Butte", [2228, 598]), ("Corson", [548, 558]), ("Dewey", [791, 1029]),
      ("Harding", [644, 41]), ("Perkins", [1193, 138]), ("Ziebach", [414, 400])],
     [5818, 2764]))
SENATE_29 = (
    ("State Senate", "29", [("Gary L. Cammack", "REP"), ("Matt Kammerer", "DEM")],
     [("Butte", [637, 209]), ("Meade", [5548, 2205]), ("Pennington", [237, 144])],
     [6422, 2558]))
SENATE_30 = (
    ("State Senate", "30", [("A. Gideon Oakes", "LIB"), ("Lance Steven Russell", "REP"),
                            ("Kristine Ina Winter", "DEM")],
     [("Custer", [824, 2340, 1123]), ("Fall River", [622, 1669, 840]),
      ("Pennington", [688, 2643, 980])],
     [2134, 6652, 2943]))
SENATE_31 = (
    ("State Senate", "31", [("Bob Ewing", "REP"), ("Sherry Bea Smith", "DEM")],
     [("Lawrence", [6962, 3710])],
     [6962, 3710]))
SENATE_32 = (
    ("State Senate", "32", [("Alan Solano", "REP"), ("Ayla Rodriguez", "DEM")],
     [("Pennington", [5602, 3404])],
     [5602, 3404]))
SENATE_33 = (
    ("State Senate", "33", [("Phil Jensen", "REP"), ("Ryan A. Ryder", "DEM")],
     [("Meade", [1397, 648]), ("Pennington", [5258, 3370])],
     [6655, 4018]))
SENATE_34 = (
    ("State Senate", "34", [("Jeff Partridge", "REP"), ("Zach VanWyk", "DEM")],
     [("Pennington", [6332, 3769])],
     [6332, 3769]))
SENATE_35 = (
    ("State Senate", "35", [("Lynne DiSanto", "REP"), ("Pat Cromwell", "DEM")],
     [("Pennington", [4323, 2650])],
     [4323, 2650]))

# --- State House (post-recount values for Districts 09, 25, 27) ---
HOUSE_1 = (
    ("State House", "1", [("Tamara St John", "REP"), ("H. Paul Dennert", "DEM"),
                          ("Steven D. McCleerey", "DEM")],
     [("Brown", [877, 839, 561]), ("Day", [1251, 1098, 1045]),
      ("Marshall", [827, 1048, 854]), ("Roberts", [1780, 1154, 1840])],
     [4735, 4139, 4300]))
HOUSE_2 = (
    ("State House", "2", [("Kaleb W. Weiss", "REP"), ("Lana J. Greenfield", "REP"),
                          ("Jenae Hansen", "DEM"), ("Mike McHugh", "DEM")],
     [("Brown", [1550, 1644, 1394, 1314]), ("Clark", [735, 974, 576, 412]),
      ("Hamlin", [1530, 1722, 707, 584]), ("Spink", [1006, 1333, 1179, 750])],
     [4821, 5673, 3856, 3060]))
HOUSE_3 = (
    ("State House", "3", [("Carl E Perry", "REP"), ("Drew Dennert", "REP"),
                          ("Brooks Briscoe", "DEM"),
                          ("Justin Roemmick", "DEM")],
     [("Brown", [4894, 5556, 3564, 3113])],
     [4894, 5556, 3564, 3113]))
HOUSE_4 = (
    ("State House", "4", [("Daryl Lamar Root", "LIB"), ("Fred Deutsch", "REP"),
                          ("John Mills", "REP"), ("Jim Chilson", "DEM"),
                          ("Kathy Tyler", "DEM")],
     [("Brookings", [208, 2095, 2060, 864, 1410]), ("Codington", [39, 824, 611, 598, 514]),
      ("Deuel", [112, 1130, 1006, 446, 806]), ("Grant", [98, 1885, 1608, 766, 1272])],
     [457, 5934, 5285, 2674, 4002]))
HOUSE_5 = (
    ("State House", "5", [("Nancy York", "REP"), ("Hugh M. Bartels", "REP"),
                          ("Brett Ries", "DEM"), ("Diana Hane", "DEM")],
     [("Codington", [5337, 5328, 3494, 1664])],
     [5337, 5328, 3494, 1664]))
HOUSE_6 = (
    ("State House", "6", [("Aaron Aylward", "LIB"), ("Isaac Latterell", "REP"),
                          ("Herman Otten", "REP"), ("Kyle Boese", "DEM"),
                          ("Nancy Kirstein", "DEM")],
     [("Lincoln", [930, 5490, 5911, 3357, 3399])],
     [930, 5490, 5911, 3357, 3399]))
HOUSE_7 = (
    ("State House", "7", [("Doug Post", "REP"), ("Tim Reed", "REP"),
                          ("Zachary Kovach", "DEM"), ('Dwight W. "Bill" Adamson', "DEM"),
                          ("Cory Ann Ellis", "IND")],
     [("Brookings", [3132, 4593, 1780, 2468, 1976])],
     [3132, 4593, 1780, 2468, 1976]))
HOUSE_8 = (
    ("State House", "8", [("Marli Wiese", "REP"), ("Randy Gross", "REP"),
                          ("Chris Francis", "DEM"), ("Jason Unger", "DEM")],
     [("Lake", [3538, 2577, 1318, 1955]), ("Miner", [647, 532, 242, 388]),
      ("Moody", [1357, 1466, 642, 1346]), ("Sanborn", [621, 598, 214, 277])],
     [6163, 5173, 2416, 3966]))
HOUSE_9 = (
    ("State House", "9", [("Deb Peters", "REP"), ("Michael Clark", "REP"),
                          ("Michael Saba", "DEM"), ("Toni Miller", "DEM")],
     [("Minnehaha", [5013, 3588, 3655, 3185])],
     [5013, 3588, 3655, 3185]))
HOUSE_10 = (
    ("State House", "10", [("Steven Haugaard", "REP"), ("Doug Barthel", "REP"),
                           ("Dean Kurtz", "DEM"), ("Barbara Saxton", "DEM")],
     [("Minnehaha", [5017, 5101, 3066, 3094])],
     [5017, 5101, 3066, 3094]))
HOUSE_11 = (
    ("State House", "11", [("Mark K. Willadsen", "REP"), ("Chris Karr", "REP"),
                           ("Sheryl L. Johnson", "DEM"), ("Margaret Kuipers", "DEM")],
     [("Minnehaha", [5436, 5227, 4450, 3769])],
     [5436, 5227, 4450, 3769]))
HOUSE_12 = (
    ("State House", "12", [("Manny Steele", "REP"), ("Arch Beal", "REP"),
                           ("Scott C. Petersen", "DEM"), ("Jeff Hayward", "DEM")],
     [("Lincoln", [2187, 2235, 1553, 1369]), ("Minnehaha", [2526, 2522, 2767, 2547])],
     [4713, 4757, 4320, 3916]))
HOUSE_13 = (
    ("State House", "13", [("Sue Peterson", "REP"), ("Rex Roling", "REP"),
                           ("Kelly Sullivan", "DEM")],
     [("Lincoln", [3081, 2632, 1801]), ("Minnehaha", [3295, 2764, 3675])],
     [6376, 5396, 5476]))
HOUSE_14 = (
    ("State House", "14", [("Larry P. Zikmund", "REP"), ("Tom Holmes", "REP"),
                           ("Valerie Loudenback", "DEM"), ("Erin Healy", "DEM")],
     [("Minnehaha", [5299, 4911, 4716, 5102])],
     [5299, 4911, 4716, 5102]))
HOUSE_15 = (
    ("State House", "15", [("Jamie Smith", "DEM"), ("Linda Duba", "DEM")],
     [("Minnehaha", [2481, 2771])],
     [2481, 2771]))
HOUSE_16 = (
    ("State House", "16", [("Kevin D. Jensen", "REP"), ("David L. Anderson", "REP"),
                           ("Mike Steinbrecher", "DEM"), ("Chad Skilies", "DEM")],
     [("Lincoln", [2087, 2096, 807, 1144]), ("Union", [4034, 3643, 1999, 1851])],
     [6121, 5739, 2806, 2995]))
HOUSE_17 = (
    ("State House", "17", [("Gregory Baldwin", "LIB"), ("Nancy Rasmussen", "REP"),
                           ("Ray Ring", "DEM"), ("John A. Gors", "DEM")],
     [("Clay", [368, 1788, 2836, 2536]), ("Turner", [461, 2586, 1516, 1071])],
     [829, 4374, 4352, 3607]))
HOUSE_18 = (
    ("State House", "18", [("Jean M. Hunhoff", "REP"), ("Max L. Farver", "REP"),
                           ("Ryan Cwach", "DEM"), ("Terry Crandall", "DEM")],
     [("Yankton", [4444, 3782, 4552, 3547])],
     [4444, 3782, 4552, 3547]))
HOUSE_19 = (
    ("State House", "19", [("Kent Peterson", "REP"), ("Kyle Schoenfish", "REP"),
                           ("John C. Koch", "DEM"), ("Alison Bowers", "IND"),
                           ("Roger Hofer", "IND")],
     [("Bon Homme", [812, 1035, 460, 216, 271]), ("Douglas", [1054, 1074, 181, 100, 176]),
      ("Hanson", [923, 939, 356, 242, 202]), ("Hutchinson", [1956, 2293, 513, 319, 513]),
      ("McCook", [1618, 1143, 604, 256, 519])],
     [6363, 6484, 2114, 1133, 1681]))
HOUSE_20 = (
    ("State House", "20", [("Paul R. Miskimins", "REP"), ("Lance Koth", "REP"),
                           ("Ione Klinger", "DEM"), ("James Schorzmann", "DEM")],
     [("Aurora", [767, 556, 441, 379]), ("Davison", [4197, 3719, 2585, 2136]),
      ("Jerauld", [465, 481, 271, 351])],
     [5429, 4756, 3297, 2866]))
HOUSE_21 = (
    ("State House", "21", [("Caleb Finck", "REP"), ("Lee Qualm", "REP"),
                           ("Faith Spotted Eagle", "DEM"), ("Anna Kerner Andersson", "DEM")],
     [("Bon Homme", [704, 674, 184, 293]), ("Charles Mix", [1682, 2098, 925, 1105]),
      ("Gregory", [1068, 1285, 325, 903]), ("Tripp", [1414, 1561, 366, 727])],
     [4868, 5618, 1800, 3028]))
HOUSE_22 = (
    ("State House", "22", [("Roger Chase", "REP"), ("Bob Glanzer", "REP"),
                           ("Tyler B. Volesky", "DEM")],
     [("Beadle", [3279, 3886, 2575]), ("Kingsbury", [1300, 1410, 913])],
     [4579, 5296, 3488]))
HOUSE_23 = (
    ("State House", "23", [("Spencer Gosch", "REP"), ("John A. Lake", "REP"),
                           ("Eleanor Iverson", "DEM"), ("Margaret Ann Walsh", "DEM")],
     [("Campbell", [638, 533, 83, 67]), ("Edmunds", [1162, 961, 370, 352]),
      ("Faulk", [700, 745, 202, 199]), ("Hand", [971, 824, 699, 405]),
      ("McPherson", [826, 696, 162, 165]), ("Potter", [804, 1061, 126, 114]),
      ("Spink", [187, 164, 89, 86]), ("Walworth", [1827, 1451, 374, 329])],
     [7115, 6435, 2105, 1717]))
HOUSE_24 = (
    ("State House", "24", [("Tim Rounds", "REP"), ("Mary Duvall", "REP"),
                           ("Terry Keller", "DEM"), ("Brian Watterson", "DEM")],
     [("Hughes", [4882, 5255, 2671, 1627]), ("Hyde", [453, 436, 159, 123]),
      ("Stanley", [905, 978, 443, 280]), ("Sully", [596, 569, 176, 107])],
     [6836, 7238, 3449, 2137]))
HOUSE_25 = (
    ("State House", "25", [("Jon Hansen", "REP"), ("Tom Pischke", "REP"),
                           ("Dan Ahlers", "DEM"), ("Bj Motley", "DEM")],
     [("Minnehaha", [5982, 5272, 5174, 2266])],
     [5982, 5272, 5174, 2266]))
HOUSE_26A = (
    ("State House", "26A", [("Shawn Bordeaux", "DEM")],
     [("Mellette", [393]), ("Todd", [1664])],
     [2057]))
HOUSE_26B = (
    ("State House", "26B", [("Rebecca Reimer", "REP"), ("Debra Smith", "DEM")],
     [("Brule", [1416, 643]), ("Buffalo", [153, 353]), ("Jones", [397, 102]),
      ("Lyman", [750, 598])],
     [2716, 1696]))
HOUSE_27 = (
    ("State House", "27", [("Steve Livermont", "REP"), ("Elizabeth May", "REP"),
                           ("Margaret Ross", "DEM"), ("Peri Pourier", "DEM")],
     [("Bennett", [713, 674, 310, 342]), ("Haakon", [826, 749, 82, 49]),
      ("Jackson", [633, 613, 254, 271]), ("Oglala Lakota", [236, 341, 2003, 2180]),
      ("Pennington", [275, 257, 24, 23])],
     [2683, 2634, 2673, 2865]))
HOUSE_28A = (
    ("State House", "28A", [("Oren Lesmeister", "DEM")],
     [("Corson", [730]), ("Dewey", [1401]), ("Ziebach", [596])],
     [2727]))
HOUSE_28B = (
    ("State House", "28B", [("Jason D. Hill", "LIB"), ("Sam Marty", "REP")],
     [("Butte", [504, 2192]), ("Harding", [47, 631]), ("Perkins", [135, 1130])],
     [686, 3953]))
HOUSE_29 = (
    ("State House", "29", [("Kirk Chaffee", "REP"), ("Thomas J. Brunner", "REP"),
                           ("Michael S. McManus", "DEM"), ("Jade Addison", "DEM")],
     [("Butte", [541, 591, 151, 155]), ("Meade", [5177, 4922, 1721, 1796]),
      ("Pennington", [217, 198, 132, 127])],
     [5935, 5711, 2004, 2078]))
HOUSE_30 = (
    ("State House", "30", [("Timothy Ray Goodwin", "REP"), ("Julie Frye-Mueller", "REP"),
                           ("Karen McGregor", "DEM"), ("Whitney Raver", "DEM")],
     [("Custer", [2702, 2538, 1149, 1076]), ("Fall River", [1925, 1951, 877, 729]),
      ("Pennington", [2806, 2677, 1126, 879])],
     [7433, 7166, 3152, 2684]))
HOUSE_31 = (
    ("State House", "31", [("Timothy R. Johns", "REP"), ("Charles M. Turbiville", "REP"),
                           ("Naveen Malik", "DEM"), ("Wyatt Osthus", "DEM")],
     [("Lawrence", [6879, 5040, 3789, 2539])],
     [6879, 5040, 3789, 2539]))
HOUSE_32 = (
    ("State House", "32", [("Scyller J. Borglum", "REP"), ("Chris Johnson", "REP"),
                           ("Susan Kelts", "DEM"), ("Bill Knight", "DEM")],
     [("Pennington", [4643, 4436, 4196, 2631])],
     [4643, 4436, 4196, 2631]))
HOUSE_33 = (
    ("State House", "33", [("David Johnson", "REP"), ("Taffy Howard", "REP"),
                           ("Lilias Jarding", "DEM"), ("Nick Reid", "IND")],
     [("Meade", [1269, 1154, 537, 468]), ("Pennington", [4825, 4508, 3000, 1848])],
     [6094, 5662, 3537, 2316]))
HOUSE_34 = (
    ("State House", "34", [("Jess Olson", "REP"), ("Michael G. Diedrich", "REP"),
                           ("George J. Nelson", "DEM"), ("Brian Davis", "DEM")],
     [("Pennington", [5853, 5848, 3502, 2987])],
     [5853, 5848, 3502, 2987]))
HOUSE_35 = (
    ("State House", "35", [("Tina L Mulally", "REP"), ("Tony Randolp", "REP"),
                           ("Bo Sistak", "DEM"), ("Michael T. Hanson", "DEM")],
     [("Pennington", [4030, 3776, 2179, 2183])],
     [4030, 3776, 2179, 2183]))

# --- West Dakota Water Development District (Pennington only, nonpartisan) ---
WDD_1 = (
    ("West Dakota Water Development District", "WDD 1",
     [("Ronald M. Koth", "NON"), ("Ken Moss", "NON")],
     [("Pennington", [1366, 1248])],
     [1366, 1248]))
WDD_3 = (
    ("West Dakota Water Development District", "WDD 3",
     [("Michael Mueller", "NON"), ("Dan Driscoll", "NON")],
     [("Pennington", [1404, 1969])],
     [1404, 1969]))
WDD_5 = (
    ("West Dakota Water Development District", "WDD 5",
     [("Ernest L. Getty", "NON"), ("Steven Rolinger", "NON")],
     [("Pennington", [1228, 1709])],
     [1228, 1709]))
WDD_9 = (
    ("West Dakota Water Development District", "WDD 9",
     [("Wyatt Rogers", "NON"), ("Linda Harris", "NON")],
     [("Pennington", [679, 1533])],
     [679, 1533]))


# --- Supreme Court retention ---
RETENTION = (
    "Supreme Court Retention", "", [("Janine M. Kern - Yes", ""), ("Janine M. Kern - No", "")],
    [
        ("Aurora", [943, 173]), ("Beadle", [4591, 863]), ("Bennett", [615, 240]),
        ("Bon Homme", [2062, 384]), ("Brookings", [8565, 1617]),
        ("Brown", [10477, 2176]), ("Brule", [1559, 297]), ("Buffalo", [298, 174]),
        ("Butte", [2761, 602]), ("Campbell", [545, 89]),
        ("Charles Mix", [2666, 532]), ("Clark", [1177, 227]), ("Clay", [3349, 661]),
        ("Codington", [7415, 1358]), ("Corson", [658, 321]), ("Custer", [3212, 647]),
        ("Davison", [5576, 887]), ("Day", [1921, 386]), ("Deuel", [1433, 306]),
        ("Dewey", [1058, 544]), ("Douglas", [1152, 148]), ("Edmunds", [1190, 243]),
        ("Fall River", [2271, 535]), ("Faulk", [762, 134]), ("Grant", [2346, 450]),
        ("Gregory", [1555, 303]), ("Haakon", [726, 131]), ("Hamlin", [1911, 333]),
        ("Hand", [1229, 221]), ("Hanson", [1159, 188]), ("Harding", [522, 80]),
        ("Hughes", [6446, 887]), ("Hutchinson", [2419, 371]), ("Hyde", [499, 91]),
        ("Jackson", [628, 235]), ("Jerauld", [655, 156]), ("Jones", [398, 87]),
        ("Kingsbury", [1814, 326]), ("Lake", [3835, 648]), ("Lawrence", [7911, 1626]),
        ("Lincoln", [17578, 2900]), ("Lyman", [952, 282]), ("Marshall", [1449, 264]),
        ("McCook", [1808, 307]), ("McPherson", [801, 117]), ("Meade", [7458, 1642]),
        ("Mellette", [472, 147]), ("Miner", [717, 151]),
        ("Minnehaha", [49072, 10305]), ("Moody", [2047, 445]),
        ("Oglala Lakota", [1453, 1259]), ("Pennington", [31059, 5877]),
        ("Perkins", [940, 200]), ("Potter", [879, 151]), ("Roberts", [2549, 615]),
        ("Sanborn", [771, 132]), ("Spink", [2075, 369]), ("Stanley", [1160, 177]),
        ("Sully", [606, 103]), ("Todd", [1155, 767]), ("Tripp", [1834, 356]),
        ("Turner", [2845, 477]), ("Union", [4962, 904]), ("Walworth", [1661, 349]),
        ("Yankton", [6310, 1347]), ("Ziebach", [477, 223]),
    ],
    [243399, 49543])


def _amendment_rows(page_a, page_b):
    """Aurora..Fall River rows from one page + Faulk..Ziebach rows from the next."""
    return page_a + page_b


AMEND_W = (
    "Constitutional Amendment W", "", [("Yes", ""), ("No", "")],
    _amendment_rows(
        [
            ("Aurora", [454, 735]), ("Beadle", [2297, 3387]), ("Bennett", [416, 610]),
            ("Bon Homme", [1087, 1475]), ("Brookings", [5296, 5770]),
            ("Brown", [5307, 8271]), ("Brule", [818, 1188]), ("Buffalo", [213, 284]),
            ("Butte", [1679, 1937]), ("Campbell", [190, 484]),
            ("Charles Mix", [1287, 2036]), ("Clark", [538, 1013]),
            ("Clay", [2357, 1984]), ("Codington", [4254, 5501]),
            ("Corson", [371, 654]), ("Custer", [2059, 2171]),
            ("Davison", [2908, 3878]), ("Day", [1054, 1491]), ("Deuel", [676, 1202]),
            ("Dewey", [805, 922]), ("Douglas", [446, 937]), ("Edmunds", [503, 1115]),
            ("Fall River", [1492, 1517]),
        ],
        [
            ("Faulk", [308, 689]), ("Grant", [1172, 1794]), ("Gregory", [735, 1305]),
            ("Haakon", [249, 663]), ("Hamlin", [956, 1580]), ("Hand", [549, 1034]),
            ("Hanson", [670, 792]), ("Harding", [200, 461]), ("Hughes", [2827, 4956]),
            ("Hutchinson", [1103, 1981]), ("Hyde", [225, 408]), ("Jackson", [374, 568]),
            ("Jerauld", [314, 533]), ("Jones", [170, 359]), ("Kingsbury", [941, 1354]),
            ("Lake", [2277, 2689]), ("Lawrence", [5724, 4731]),
            ("Lincoln", [9995, 12305]), ("Lyman", [542, 775]), ("Marshall", [643, 1191]),
            ("McCook", [931, 1380]), ("McPherson", [265, 724]), ("Meade", [4419, 5301]),
            ("Mellette", [252, 394]), ("Miner", [397, 620]),
            ("Minnehaha", [31093, 33941]), ("Moody", [1154, 1547]),
            ("Oglala Lakota", [1509, 1213]), ("Pennington", [20452, 18732]),
            ("Perkins", [394, 895]), ("Potter", [300, 843]), ("Roberts", [1519, 1956]),
            ("Sanborn", [350, 604]), ("Spink", [949, 1720]), ("Stanley", [553, 891]),
            ("Sully", [246, 541]), ("Todd", [957, 1041]), ("Tripp", [799, 1444]),
            ("Turner", [1376, 2233]), ("Union", [3066, 3210]),
            ("Walworth", [660, 1484]), ("Yankton", [4340, 4207]),
            ("Ziebach", [307, 430]),
        ],
    ),
    [142769, 174081])


AMEND_X = (
    "Constitutional Amendment X", "", [("Yes", ""), ("No", "")],
    _amendment_rows(
        [
            ("Aurora", [482, 640]), ("Beadle", [2383, 3051]), ("Bennett", [463, 557]),
            ("Bon Homme", [1050, 1337]), ("Brookings", [4742, 5580]),
            ("Brown", [5510, 6955]), ("Brule", [865, 1130]), ("Buffalo", [252, 237]),
            ("Butte", [1644, 2011]), ("Campbell", [277, 344]),
            ("Charles Mix", [1459, 1816]), ("Clark", [723, 798]),
            ("Clay", [1696, 2379]), ("Codington", [4323, 4808]),
            ("Corson", [464, 556]), ("Custer", [2067, 2168]),
            ("Davison", [2999, 3416]), ("Day", [987, 1549]), ("Deuel", [737, 1002]),
            ("Dewey", [780, 942]), ("Douglas", [641, 731]), ("Edmunds", [654, 915]),
            ("Fall River", [1473, 1541]),
        ],
        [
            ("Faulk", [432, 535]), ("Grant", [1337, 1476]), ("Gregory", [850, 1133]),
            ("Haakon", [359, 492]), ("Hamlin", [1140, 1379]), ("Hand", [680, 870]),
            ("Hanson", [641, 806]), ("Harding", [295, 329]), ("Hughes", [3292, 4364]),
            ("Hutchinson", [1490, 1566]), ("Hyde", [230, 399]), ("Jackson", [424, 504]),
            ("Jerauld", [323, 484]), ("Jones", [237, 284]), ("Kingsbury", [904, 1259]),
            ("Lake", [2136, 2783]), ("Lawrence", [4826, 5514]),
            ("Lincoln", [9925, 11193]), ("Lyman", [569, 695]), ("Marshall", [731, 990]),
            ("McCook", [1035, 1294]), ("McPherson", [515, 470]), ("Meade", [4432, 4967]),
            ("Mellette", [279, 353]), ("Miner", [414, 577]),
            ("Minnehaha", [29218, 34924]), ("Moody", [1141, 1509]),
            ("Oglala Lakota", [1367, 1418]), ("Pennington", [18145, 20496]),
            ("Perkins", [567, 643]), ("Potter", [498, 626]), ("Roberts", [1515, 1963]),
            ("Sanborn", [349, 532]), ("Spink", [1146, 1462]), ("Stanley", [571, 867]),
            ("Sully", [375, 404]), ("Todd", [968, 982]), ("Tripp", [919, 1247]),
            ("Turner", [1545, 1894]), ("Union", [3176, 3074]),
            ("Walworth", [945, 1103]), ("Yankton", [3819, 4644]),
            ("Ziebach", [299, 395]),
        ],
    ),
    [140730, 167362])


AMEND_Z = (
    "Constitutional Amendment Z", "", [("Yes", ""), ("No", "")],
    _amendment_rows(
        [
            ("Aurora", [674, 528]), ("Beadle", [3309, 2437]), ("Bennett", [566, 449]),
            ("Bon Homme", [1480, 1080]), ("Brookings", [6932, 4075]),
            ("Brown", [7901, 5530]), ("Brule", [1208, 788]), ("Buffalo", [292, 193]),
            ("Butte", [2385, 1269]), ("Campbell", [353, 306]),
            ("Charles Mix", [1846, 1413]), ("Clark", [937, 581]),
            ("Clay", [2612, 1705]), ("Codington", [5979, 3638]),
            ("Corson", [576, 479]), ("Custer", [2921, 1286]),
            ("Davison", [4168, 2620]), ("Day", [1384, 1147]), ("Deuel", [1106, 754]),
            ("Dewey", [939, 777]), ("Douglas", [762, 623]), ("Edmunds", [877, 700]),
            ("Fall River", [2061, 973]),
        ],
        [
            ("Faulk", [558, 412]), ("Grant", [1816, 1180]), ("Gregory", [1126, 872]),
            ("Haakon", [458, 452]), ("Hamlin", [1472, 1016]), ("Hand", [867, 690]),
            ("Hanson", [941, 512]), ("Harding", [414, 251]), ("Hughes", [4422, 3242]),
            ("Hutchinson", [1871, 1163]), ("Hyde", [346, 288]), ("Jackson", [513, 421]),
            ("Jerauld", [451, 394]), ("Jones", [285, 239]), ("Kingsbury", [1320, 968]),
            ("Lake", [2982, 1895]), ("Lawrence", [7090, 3305]),
            ("Lincoln", [14233, 7963]), ("Lyman", [699, 603]), ("Marshall", [1005, 825]),
            ("McCook", [1442, 852]), ("McPherson", [495, 490]), ("Meade", [6440, 3323]),
            ("Mellette", [382, 293]), ("Miner", [502, 476]),
            ("Minnehaha", [40801, 22817]), ("Moody", [1590, 1074]),
            ("Oglala Lakota", [1554, 1246]), ("Pennington", [25931, 12567]),
            ("Perkins", [746, 533]), ("Potter", [606, 519]), ("Roberts", [2067, 1404]),
            ("Sanborn", [502, 447]), ("Spink", [1508, 1117]), ("Stanley", [788, 625]),
            ("Sully", [461, 322]), ("Todd", [1165, 899]), ("Tripp", [1295, 1027]),
            ("Turner", [2184, 1439]), ("Union", [4248, 2027]),
            ("Walworth", [1187, 982]), ("Yankton", [5393, 3046]),
            ("Ziebach", [366, 380]),
        ],
    ),
    [195790, 117947])


IM_24 = (
    "Initiated Measure 24", "", [("Yes", ""), ("No", "")],
    _amendment_rows(
        [
            ("Aurora", [601, 606]), ("Beadle", [3028, 2733]), ("Bennett", [497, 523]),
            ("Bon Homme", [1270, 1312]), ("Brookings", [6313, 4746]),
            ("Brown", [6889, 6607]), ("Brule", [1058, 948]), ("Buffalo", [239, 251]),
            ("Butte", [2086, 1587]), ("Campbell", [299, 360]),
            ("Charles Mix", [1585, 1730]), ("Clark", [772, 753]),
            ("Clay", [2431, 1891]), ("Codington", [5640, 4035]),
            ("Corson", [486, 589]), ("Custer", [2384, 1801]),
            ("Davison", [3821, 3019]), ("Day", [1297, 1270]), ("Deuel", [934, 928]),
            ("Dewey", [818, 916]), ("Douglas", [661, 729]), ("Edmunds", [754, 838]),
            ("Fall River", [1800, 1232]),
        ],
        [
            ("Faulk", [472, 503]), ("Grant", [1583, 1433]), ("Gregory", [942, 1062]),
            ("Haakon", [365, 540]), ("Hamlin", [1275, 1234]), ("Hand", [778, 799]),
            ("Hanson", [848, 615]), ("Harding", [345, 324]), ("Hughes", [3790, 3914]),
            ("Hutchinson", [1599, 1472]), ("Hyde", [286, 351]), ("Jackson", [438, 501]),
            ("Jerauld", [366, 478]), ("Jones", [236, 285]), ("Kingsbury", [1075, 1167]),
            ("Lake", [2671, 2215]), ("Lawrence", [6383, 3956]),
            ("Lincoln", [12846, 9516]), ("Lyman", [657, 654]), ("Marshall", [928, 911]),
            ("McCook", [1222, 1092]), ("McPherson", [408, 582]), ("Meade", [5622, 4136]),
            ("Mellette", [296, 375]), ("Miner", [482, 505]),
            ("Minnehaha", [37416, 26717]), ("Moody", [1392, 1261]),
            ("Oglala Lakota", [1385, 1440]), ("Pennington", [23628, 15061]),
            ("Perkins", [647, 640]), ("Potter", [472, 664]), ("Roberts", [1807, 1677]),
            ("Sanborn", [470, 485]), ("Spink", [1342, 1301]), ("Stanley", [720, 710]),
            ("Sully", [399, 388]), ("Todd", [1003, 1070]), ("Tripp", [1056, 1181]),
            ("Turner", [1920, 1713]), ("Union", [3597, 2628]),
            ("Walworth", [1019, 1133]), ("Yankton", [4780, 3659]),
            ("Ziebach", [331, 420]),
        ],
    ),
    [174960, 140172])


IM_25 = (
    "Initiated Measure 25", "", [("Yes", ""), ("No", "")],
    _amendment_rows(
        [
            ("Aurora", [456, 804]), ("Beadle", [2626, 3373]), ("Bennett", [301, 768]),
            ("Bon Homme", [1054, 1634]), ("Brookings", [5544, 6035]),
            ("Brown", [6105, 8003]), ("Brule", [864, 1212]), ("Buffalo", [175, 344]),
            ("Butte", [1367, 2399]), ("Campbell", [244, 459]),
            ("Charles Mix", [1459, 2023]), ("Clark", [616, 999]),
            ("Clay", [2312, 2199]), ("Codington", [4382, 6054]),
            ("Corson", [379, 716]), ("Custer", [1759, 2579]),
            ("Davison", [3389, 3776]), ("Day", [1112, 1586]), ("Deuel", [758, 1187]),
            ("Dewey", [601, 1188]), ("Douglas", [581, 878]), ("Edmunds", [645, 1022]),
            ("Fall River", [1163, 1962]),
        ],
        [
            ("Faulk", [432, 611]), ("Grant", [1350, 1800]), ("Gregory", [809, 1296]),
            ("Haakon", [282, 649]), ("Hamlin", [974, 1668]), ("Hand", [716, 912]),
            ("Hanson", [766, 772]), ("Harding", [139, 539]), ("Hughes", [3596, 4343]),
            ("Hutchinson", [1476, 1734]), ("Hyde", [262, 389]), ("Jackson", [258, 705]),
            ("Jerauld", [343, 549]), ("Jones", [178, 362]), ("Kingsbury", [969, 1429]),
            ("Lake", [2175, 2927]), ("Lawrence", [4817, 5922]),
            ("Lincoln", [12464, 11206]), ("Lyman", [553, 820]), ("Marshall", [785, 1145]),
            ("McCook", [1067, 1378]), ("McPherson", [308, 713]), ("Meade", [4128, 5989]),
            ("Mellette", [269, 433]), ("Miner", [416, 650]),
            ("Minnehaha", [34059, 34542]), ("Moody", [1125, 1672]),
            ("Oglala Lakota", [1019, 1844]), ("Pennington", [18838, 21801]),
            ("Perkins", [362, 962]), ("Potter", [432, 762]), ("Roberts", [1508, 2156]),
            ("Sanborn", [432, 570]), ("Spink", [1201, 1540]), ("Stanley", [568, 915]),
            ("Sully", [284, 518]), ("Todd", [795, 1361]), ("Tripp", [941, 1501]),
            ("Turner", [1617, 2164]), ("Union", [3132, 3361]),
            ("Walworth", [762, 1458]), ("Yankton", [4040, 4836]),
            ("Ziebach", [236, 550]),
        ],
    ),
    [148775, 182654])


ALL_CONTESTS = [
    US_HOUSE, GOVERNOR, SOS, AG, AUDITOR, TREASURER, LANDS, PUC,
] + [
    SENATE_1, SENATE_2, SENATE_3, SENATE_4, SENATE_5, SENATE_6, SENATE_7, SENATE_8,
    SENATE_9, SENATE_10, SENATE_11, SENATE_12, SENATE_13, SENATE_14, SENATE_15,
    SENATE_16, SENATE_17, SENATE_18, SENATE_19, SENATE_20, SENATE_21, SENATE_22,
    SENATE_23, SENATE_24, SENATE_25, SENATE_26, SENATE_27, SENATE_28, SENATE_29,
    SENATE_30, SENATE_31, SENATE_32, SENATE_33, SENATE_34, SENATE_35,
] + [
    HOUSE_1, HOUSE_2, HOUSE_3, HOUSE_4, HOUSE_5, HOUSE_6, HOUSE_7, HOUSE_8,
    HOUSE_9, HOUSE_10, HOUSE_11, HOUSE_12, HOUSE_13, HOUSE_14, HOUSE_15, HOUSE_16,
    HOUSE_17, HOUSE_18, HOUSE_19, HOUSE_20, HOUSE_21, HOUSE_22, HOUSE_23, HOUSE_24,
    HOUSE_25, HOUSE_26A, HOUSE_26B, HOUSE_27, HOUSE_28A, HOUSE_28B, HOUSE_29,
    HOUSE_30, HOUSE_31, HOUSE_32, HOUSE_33, HOUSE_34, HOUSE_35,
] + [
    WDD_1, WDD_3, WDD_5, WDD_9, RETENTION, AMEND_W, AMEND_X, AMEND_Z, IM_24, IM_25,
]
