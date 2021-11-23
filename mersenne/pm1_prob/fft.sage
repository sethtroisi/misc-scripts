'''
  Data from James in https://www.mersenneforum.org/showpost.php?p=593701&postcount=707

  timings from these posts:
   http://www.mersenneforum.org/showpost.php?p=152289&postcount=207 // Dec-2008
   http://www.mersenneforum.org/showpost.php?p=258827&postcount=519 // Apr-2011
   and then interpolated for new FFT sizes as listed in gwnum/mult.asm [17-Apr-2011]

  Rule-Of-Thumb scaling: FFT 8x bigger gives 10x longer runtime
   scaling of run time is ~ p^2.1, iteration count is p^1, so time/iteration is ~ p^1.1.
   kriesel added the 64M and 50M row 8/23/19 based on scaling of some values found in prime95 v29.8b3 mult.asm to match at 32M
   kriesel added >64-192M rows 12/26/19 [added to mersenne.ca on 2020-09-23] based on p^1.1 scaling approximation for gpuowl etc extension
   James added estimated 192M-256M 2020-09-23 based on p^1.1
'''
fft_timing_data = [
    (268435456, 25.105), (251658240, 23.385), (234881024, 21.676), (218103808, 19.979),
    (201326592, 18.295), (184549376, 16.626), (167772160, 14.971), (150994944, 13.332),
    (117440512, 10.112), (100663296, 8.5350), (92274688, 7.7560), (83886080, 6.9840),
    (75497472, 6.2200), (67108864, 5.4640), (62914560, 5.0380), (58982400, 4.6110),
    (56623104, 4.0980), (52428800, 3.7568), (45875200, 3.3300), (41943040, 2.9880),
    (39321600, 2.8010), (36700160, 2.6130), (33554432, 2.3832), (33030144, 2.3577),
    (32768000, 2.3449), (31457280, 2.2812), (29360128, 2.1792), (28311552, 2.0898),
    (27525120, 2.0227), (26214400, 1.9110), (25165824, 1.8216), (23592960, 1.6974),
    (22937600, 1.6456), (22020096, 1.5732), (20971520, 1.4904), (19660800, 1.3621),
    (18874368, 1.2852), (18350080, 1.2339), (16777216, 1.0800), (16515072, 1.0680),
    (16384000, 1.0620), (15728640, 1.0320), (14680064, 9.8400E-1), (14155776, 9.4080E-1),
    (13762560, 9.0840E-1), (13107200, 8.5440E-1), (12582912, 8.1120E-1), (11796480, 7.5900E-1),
    (11468800, 7.3725E-1), (11010048, 7.0680E-1), (10485760, 6.7200E-1), (9830400, 6.1950E-1),
    (9437184, 5.8800E-1), (9175040, 5.6700E-1), (8388608, 5.0400E-1), (8257536, 4.9830E-1),
    (8192000, 4.9545E-1), (7864320, 4.8120E-1), (7340032, 4.5840E-1), (7077888, 4.3860E-1),
    (6881280, 4.2375E-1), (6553600, 3.9900E-1), (6291456, 3.7920E-1), (5898240, 3.5436E-1),
    (5734400, 3.4401E-1), (5505024, 3.2952E-1), (5242880, 3.1296E-1), (4915200, 2.9128E-1),
    (4718592, 2.7828E-1), (4587520, 2.6961E-1), (4194304, 2.4360E-1), (4128768, 2.4045E-1),
    (4096000, 2.3887E-1), (3932160, 2.3100E-1), (3670016, 2.1840E-1), (3538944, 2.0958E-1),
    (3440640, 2.0296E-1), (3276800, 1.9194E-1), (3145728, 1.8312E-1), (2949120, 1.7070E-1),
    (2867200, 1.6552E-1), (2752512, 1.5828E-1), (2621440, 1.5000E-1), (2457600, 1.3867E-1),
    (2359296, 1.3188E-1), (2293760, 1.2735E-1), (2097152, 1.1376E-1), (2064384, 1.1232E-1),
    (2048000, 1.1160E-1), (1966080, 1.0800E-1), (1835008, 1.0224E-1), (1769472, 9.8160E-2),
    (1720320, 9.5100E-2), (1638400, 9.0000E-2), (1572864, 8.5920E-2), (1474560, 7.9980E-2),
    (1376256, 7.4040E-2), (1310720, 7.0080E-2), (1228800, 6.5655E-2), (1179648, 6.3000E-2),
    (1146880, 6.1230E-2), (1048576, 5.5920E-2), (1032192, 5.5080E-2), (983040, 5.2560E-2),
    (917504, 4.9200E-2), (884736, 4.7244E-2), (819200, 4.3332E-2), (786432, 4.1376E-2),
    (737280, 3.8334E-2), (688128, 3.5292E-2), (655360, 3.3264E-2), (589824, 2.9232E-2),
    (573440, 2.8224E-2), (524288, 2.5200E-2), (491520, 2.3880E-2), (458752, 2.2560E-2),
    (409600, 1.9770E-2), (393216, 1.8840E-2), (344064, 1.6194E-2), (327680, 1.5312E-2),
    (294912, 1.3644E-2), (262144, 1.1976E-2), (245760, 1.1376E-2), (229376, 1.0776E-2),
    (196608, 9.0744E-3), (163840, 7.3536E-3), (147456, 6.6732E-3), (131072, 5.9928E-3),
    (122880, 5.8368E-3), (114688, 5.6808E-3), (98304, 4.6872E-3), (86016, 4.0662E-3),
    (81920, 3.8592E-3), (73728, 3.2988E-3), (65536, 2.7384E-3), (61440, 2.6496E-3),
    (57344, 2.5608E-3), (49152, 2.0952E-3), (40960, 1.7256E-3), (32768, 1.3128E-3),
    (28672, 1.2600E-3), (24576, 1.0176E-3), (20480, 8.3760E-4), (16384, 6.1440E-4),
    (14336, 5.9040E-4), (12288, 4.8480E-4), (10240, 3.9840E-4), (8192, 2.8560E-4),
    (7168, 2.7600E-4), (6144, 2.2560E-4), (5120, 1.9200E-4), (4096, 1.2960E-4),
    (3584, 1.2648E-4), (3072, 1.0248E-4), (2560, 8.5200E-5), (2048, 6.1680E-5),
    (1792, 5.6880E-5), (1536, 4.7592E-5), (1280, 3.9120E-5), (1024, 2.7648E-5),
    (896, 2.5416E-5), (768, 2.0592E-5), (640, 1.7040E-5), (512, 1.1328E-5),
    (448, 1.0536E-5), (384, 8.7840E-6), (320, 7.3440E-6), (256, 5.4744E-6),
    (224, 5.2512E-6), (192, 4.2936E-6), (160, 3.5640E-6), (128, 2.5272E-6),
    (112, 2.4624E-6), (96, 2.0520E-6), (80, 1.7592E-6), (64, 1.4088E-6),
    (48, 1.1400E-6), (32, 8.7840E-7),
]
assert fft_timing_data == sorted(fft_timing_data, reverse=True)

'''
derived from gwnum/mult.asm
 2020-09-23 - added values from FFT 32M to 256M (exponents ~600M-4700M)
'''
fft_size_data = [
    (0, 32), (743, 32), (1099, 48), (1469, 64), (1827, 80), (2179, 96), (2539, 112),
    (2905, 128), (3613, 160), (4311, 192), (5029, 224), (5755, 256), (7149, 320),
    (8527, 384), (9933, 448), (11359, 512), (14119, 640), (16839, 768), (19639, 896),
    (22477, 1024), (27899, 1280), (33289, 1536), (38799, 1792), (44339, 2048), (55099, 2560),
    (65729, 3072), (76559, 3584), (87549, 4096), (108800, 5120), (129900, 6144), (151300, 7168),
    (172700, 8192), (214400, 10240), (255300, 12288), (297300, 14336), (340400, 16384),
    (423300, 20480), (504600, 24576), (587500, 28672), (671400, 32768), (835200, 40960),
    (995500, 49152), (1158000, 57344), (1243000, 61440), (1325000, 65536), (1485000, 73728),
    (1648000, 81920), (1725000, 86016), (1966000, 98304), (2287000, 114688), (2452000, 122880),
    (2614000, 131072), (2929000, 147456), (3251000, 163840), (3875000, 196608), (4512000, 229376),
    (4837000, 245760), (5158000, 262144), (5781000, 294912), (6421000, 327680), (6716000, 344064),
    (7651000, 393216), (7967000, 409600), (8908000, 458752), (9547000, 491520), (10180000, 524288),
    (11100000, 573440), (11410000, 589824), (12650000, 655360), (13250000, 688128),
    (14160000, 737280), (15070000, 786432), (15690000, 819200), (16930000, 884736),
    (17550000, 917504), (18800000, 983040), (19740000, 1032192), (20050000, 1048576),
    (21850000, 1146880), (22490000, 1179648), (23360000, 1228800), (24930000, 1310720),
    (26120000, 1376256), (27900000, 1474560), (29690000, 1572864), (30900000, 1638400),
    (32420000, 1720320), (33370000, 1769472), (34560000, 1835008), (37030000, 1966080),
    (38570000, 2048000), (38880000, 2064384), (39500000, 2097152), (43060000, 2293760),
    (44250000, 2359296), (46030000, 2457600), (49100000, 2621440), (51450000, 2752512),
    (53460000, 2867200), (54950000, 2949120), (58520000, 3145728), (60940000, 3276800),
    (63970000, 3440640), (65790000, 3538944), (68130000, 3670016), (73060000, 3932160),
    (76090000, 4096000), (76680000, 4128768), (77910000, 4194304), (84920000, 4587520),
    (87250000, 4718592), (90760000, 4915200), (96830000, 5242880), (101200000, 5505024),
    (105300000, 5734400), (108200000, 5898240), (115300000, 6291456), (120000000, 6553600),
    (126000000, 6881280), (129500000, 7077888), (134200000, 7340032), (143800000, 7864320),
    (149800000, 8192000), (151000000, 8257536), (153400000, 8388608), (167200000, 9175040),
    (172000000, 9437184), (178300000, 9830400), (190700000, 10485760), (199500000, 11010048),
    (207600000, 11468800), (213400000, 11796480), (227300000, 12582912), (236700000, 13107200),
    (248400000, 13762560), (255500000, 14155776), (264600000, 14680064), (283900000, 15728640),
    (295500000, 16384000), (297800000, 16515072), (302600000, 16777216), (329800000, 18350080),
    (339300000, 18874368), (352500000, 19660800), (376100000, 20971520), (393800000, 22020096),
    (409300000, 22937600), (420700000, 23592960), (448000000, 25165824), (467600000, 26214400),
    (488400000, 27525120), (503500000, 28311552), (521500000, 29360128), (559300000, 31457280),
    (582200000, 32768000), (585300000, 33030144), (596000000, 33554432), (605312500, 34078720),
    (614625000, 34603008), (623937500, 35127296), (633250000, 35651584), (642562500, 36175872),
    (651875000, 36700160), (661187500, 37224448), (670500000, 37748736), (679812500, 38273024),
    (689125000, 38797312), (698437500, 39321600), (707750000, 39845888), (717062500, 40370176),
    (726375000, 40894464), (735687500, 41418752), (745000000, 41943040), (754312500, 42467328),
    (763625000, 42991616), (772937500, 43515904), (782250000, 44040192), (791562500, 44564480),
    (800875000, 45088768), (810187500, 45613056), (819500000, 46137344), (828812500, 46661632),
    (838125000, 47185920), (847437500, 47710208), (856750000, 48234496), (866062500, 48758784),
    (875375000, 49283072), (884687500, 49807360), (894000000, 50331648), (903312500, 50855936),
    (912625000, 51380224), (921937500, 51904512), (931250000, 52428800), (940562500, 52953088),
    (949875000, 53477376), (959187500, 54001664), (968500000, 54525952), (977812500, 55050240),
    (987125000, 55574528), (996437500, 56098816), (1005750000, 56623104), (1015062500, 57147392),
    (1024375000, 57671680), (1033687500, 58195968), (1043000000, 58720256), (1052312500, 59244544),
    (1061625000, 59768832), (1070937500, 60293120), (1080250000, 60817408), (1089562500, 61341696),
    (1098875000, 61865984), (1108187500, 62390272), (1117500000, 62914560), (1126812500, 63438848),
    (1136125000, 63963136), (1145437500, 64487424), (1154750000, 65011712), (1164062500, 65536000),
    (1173375000, 66060288), (1182687500, 66584576), (1192000000, 67108864), (1201312500, 67633152),
    (1210625000, 68157440), (1219937500, 68681728), (1229250000, 69206016), (1238562500, 69730304),
    (1247875000, 70254592), (1257187500, 70778880), (1266500000, 71303168), (1275812500, 71827456),
    (1285125000, 72351744), (1294437500, 72876032), (1303750000, 73400320), (1313062500, 73924608),
    (1322375000, 74448896), (1331687500, 74973184), (1341000000, 75497472), (1350312500, 76021760),
    (1359625000, 76546048), (1368937500, 77070336), (1378250000, 77594624), (1387562500, 78118912),
    (1396875000, 78643200), (1406187500, 79167488), (1415500000, 79691776), (1424812500, 80216064),
    (1434125000, 80740352), (1443437500, 81264640), (1452750000, 81788928), (1462062500, 82313216),
    (1471375000, 82837504), (1480687500, 83361792), (1490000000, 83886080), (1499312500, 84410368),
    (1508625000, 84934656), (1517937500, 85458944), (1527250000, 85983232), (1536562500, 86507520),
    (1545875000, 87031808), (1555187500, 87556096), (1564500000, 88080384), (1573812500, 88604672),
    (1583125000, 89128960), (1592437500, 89653248), (1601750000, 90177536), (1611062500, 90701824),
    (1620375000, 91226112), (1629687500, 91750400), (1639000000, 92274688), (1648312500, 92798976),
    (1657625000, 93323264), (1666937500, 93847552), (1676250000, 94371840), (1685562500, 94896128),
    (1694875000, 95420416), (1704187500, 95944704), (1713500000, 96468992), (1722812500, 96993280),
    (1732125000, 97517568), (1741437500, 98041856), (1750750000, 98566144), (1760062500, 99090432),
    (1769375000, 99614720), (1778687500, 100139008), (1788000000, 100663296), (1797312500, 101187584),
    (1806625000, 101711872), (1815937500, 102236160), (1825250000, 102760448), (1834562500, 103284736),
    (1843875000, 103809024), (1853187500, 104333312), (1862500000, 104857600), (1871812500, 105381888),
    (1881125000, 105906176), (1890437500, 106430464), (1899750000, 106954752), (1909062500, 107479040),
    (1918375000, 108003328), (1927687500, 108527616), (1937000000, 109051904), (1946312500, 109576192),
    (1955625000, 110100480), (1964937500, 110624768), (1974250000, 111149056), (1983562500, 111673344),
    (1992875000, 112197632), (2002187500, 112721920), (2011500000, 113246208), (2020812500, 113770496),
    (2030125000, 114294784), (2039437500, 114819072), (2048750000, 115343360), (2058062500, 115867648),
    (2067375000, 116391936), (2076687500, 116916224), (2086000000, 117440512), (2095312500, 117964800),
    (2104625000, 118489088), (2113937500, 119013376), (2123250000, 119537664), (2132562500, 120061952),
    (2141875000, 120586240), (2151187500, 121110528), (2160500000, 121634816), (2169812500, 122159104),
    (2179125000, 122683392), (2188437500, 123207680), (2197750000, 123731968), (2207062500, 124256256),
    (2216375000, 124780544), (2225687500, 125304832), (2235000000, 125829120), (2244312500, 126353408),
    (2253625000, 126877696), (2262937500, 127401984), (2272250000, 127926272), (2281562500, 128450560),
    (2290875000, 128974848), (2300187500, 129499136), (2309500000, 130023424), (2318812500, 130547712),
    (2328125000, 131072000), (2337437500, 131596288), (2346750000, 132120576), (2356062500, 132644864),
    (2365375000, 133169152), (2374687500, 133693440), (2384000000, 134217728), (2393312500, 134742016),
    (2402625000, 135266304), (2411937500, 135790592), (2421250000, 136314880), (2430562500, 136839168),
    (2439875000, 137363456), (2449187500, 137887744), (2458500000, 138412032), (2467812500, 138936320),
    (2477125000, 139460608), (2486437500, 139984896), (2495750000, 140509184), (2505062500, 141033472),
    (2514375000, 141557760), (2523687500, 142082048), (2533000000, 142606336), (2542312500, 143130624),
    (2551625000, 143654912), (2560937500, 144179200), (2570250000, 144703488), (2579562500, 145227776),
    (2588875000, 145752064), (2598187500, 146276352), (2607500000, 146800640), (2616812500, 147324928),
    (2626125000, 147849216), (2635437500, 148373504), (2644750000, 148897792), (2654062500, 149422080),
    (2663375000, 149946368), (2672687500, 150470656), (2682000000, 150994944), (2691312500, 151519232),
    (2700625000, 152043520), (2709937500, 152567808), (2719250000, 153092096), (2728562500, 153616384),
    (2737875000, 154140672), (2747187500, 154664960), (2756500000, 155189248), (2765812500, 155713536),
    (2775125000, 156237824), (2784437500, 156762112), (2793750000, 157286400), (2803062500, 157810688),
    (2812375000, 158334976), (2821687500, 158859264), (2831000000, 159383552), (2840312500, 159907840),
    (2849625000, 160432128), (2858937500, 160956416), (2868250000, 161480704), (2877562500, 162004992),
    (2886875000, 162529280), (2896187500, 163053568), (2905500000, 163577856), (2914812500, 164102144),
    (2924125000, 164626432), (2933437500, 165150720), (2942750000, 165675008), (2952062500, 166199296),
    (2961375000, 166723584), (2970687500, 167247872), (2980000000, 167772160), (2989312500, 168296448),
    (2998625000, 168820736), (3007937500, 169345024), (3017250000, 169869312), (3026562500, 170393600),
    (3035875000, 170917888), (3045187500, 171442176), (3054500000, 171966464), (3063812500, 172490752),
    (3073125000, 173015040), (3082437500, 173539328), (3091750000, 174063616), (3101062500, 174587904),
    (3110375000, 175112192), (3119687500, 175636480), (3129000000, 176160768), (3138312500, 176685056),
    (3147625000, 177209344), (3156937500, 177733632), (3166250000, 178257920), (3175562500, 178782208),
    (3184875000, 179306496), (3194187500, 179830784), (3203500000, 180355072), (3212812500, 180879360),
    (3222125000, 181403648), (3231437500, 181927936), (3240750000, 182452224), (3250062500, 182976512),
    (3259375000, 183500800), (3268687500, 184025088), (3278000000, 184549376), (3287312500, 185073664),
    (3296625000, 185597952), (3305937500, 186122240), (3315250000, 186646528), (3324562500, 187170816),
    (3333875000, 187695104), (3343187500, 188219392), (3352500000, 188743680), (3361812500, 189267968),
    (3371125000, 189792256), (3380437500, 190316544), (3389750000, 190840832), (3399062500, 191365120),
    (3408375000, 191889408), (3417687500, 192413696), (3427000000, 192937984), (3436312500, 193462272),
    (3445625000, 193986560), (3454937500, 194510848), (3464250000, 195035136), (3473562500, 195559424),
    (3482875000, 196083712), (3492187500, 196608000), (3501500000, 197132288), (3510812500, 197656576),
    (3520125000, 198180864), (3529437500, 198705152), (3538750000, 199229440), (3548062500, 199753728),
    (3557375000, 200278016), (3566687500, 200802304), (3576000000, 201326592), (3585312500, 201850880),
    (3594625000, 202375168), (3603937500, 202899456), (3613250000, 203423744), (3622562500, 203948032),
    (3631875000, 204472320), (3641187500, 204996608), (3650500000, 205520896), (3659812500, 206045184),
    (3669125000, 206569472), (3678437500, 207093760), (3687750000, 207618048), (3697062500, 208142336),
    (3706375000, 208666624), (3715687500, 209190912), (3725000000, 209715200), (3734312500, 210239488),
    (3743625000, 210763776), (3752937500, 211288064), (3762250000, 211812352), (3771562500, 212336640),
    (3780875000, 212860928), (3790187500, 213385216), (3799500000, 213909504), (3808812500, 214433792),
    (3818125000, 214958080), (3827437500, 215482368), (3836750000, 216006656), (3846062500, 216530944),
    (3855375000, 217055232), (3864687500, 217579520), (3874000000, 218103808), (3883312500, 218628096),
    (3892625000, 219152384), (3901937500, 219676672), (3911250000, 220200960), (3920562500, 220725248),
    (3929875000, 221249536), (3939187500, 221773824), (3948500000, 222298112), (3957812500, 222822400),
    (3967125000, 223346688), (3976437500, 223870976), (3985750000, 224395264), (3995062500, 224919552),
    (4004375000, 225443840), (4013687500, 225968128), (4023000000, 226492416), (4032312500, 227016704),
    (4041625000, 227540992), (4050937500, 228065280), (4060250000, 228589568), (4069562500, 229113856),
    (4078875000, 229638144), (4088187500, 230162432), (4097500000, 230686720), (4106812500, 231211008),
    (4116125000, 231735296), (4125437500, 232259584), (4134750000, 232783872), (4144062500, 233308160),
    (4153375000, 233832448), (4162687500, 234356736), (4172000000, 234881024), (4181312500, 235405312),
    (4190625000, 235929600), (4199937500, 236453888), (4209250000, 236978176), (4218562500, 237502464),
    (4227875000, 238026752), (4237187500, 238551040), (4246500000, 239075328), (4255812500, 239599616),
    (4265125000, 240123904), (4274437500, 240648192), (4283750000, 241172480), (4293062500, 241696768),
    (4302375000, 242221056), (4311687500, 242745344), (4321000000, 243269632), (4330312500, 243793920),
    (4339625000, 244318208), (4348937500, 244842496), (4358250000, 245366784), (4367562500, 245891072),
    (4376875000, 246415360), (4386187500, 246939648), (4395500000, 247463936), (4404812500, 247988224),
    (4414125000, 248512512), (4423437500, 249036800), (4432750000, 249561088), (4442062500, 250085376),
    (4451375000, 250609664), (4460687500, 251133952), (4470000000, 251658240), (4479312500, 252182528),
    (4488625000, 252706816), (4497937500, 253231104), (4507250000, 253755392), (4516562500, 254279680),
    (4525875000, 254803968), (4535187500, 255328256), (4544500000, 255852544), (4553812500, 256376832),
    (4563125000, 256901120), (4572437500, 257425408), (4581750000, 257949696), (4591062500, 258473984),
    (4600375000, 258998272), (4609687500, 259522560), (4619000000, 260046848), (4628312500, 260571136),
    (4637625000, 261095424), (4646937500, 261619712), (4656250000, 262144000), (4665562500, 262668288),
    (4674875000, 263192576), (4684187500, 263716864), (4693500000, 264241152), (4702812500, 264765440),
    (4712125000, 265289728), (4721437500, 265814016), (4730750000, 266338304), (4740062500, 266862592),
    (4749375000, 267386880), (4758687500, 267911168), (4768000000, 268435456),
]
assert fft_size_data == sorted(fft_size_data)