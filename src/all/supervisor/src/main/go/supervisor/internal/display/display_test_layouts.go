package display

// noinspection GoSnakeCaseUsage
var (
	displayCompactASCIISoloHost_57x10_0_3 = `
+= labnode-one ================================== vESC =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
`
	displayCompactASCIISoloHost_58x10_1_3 = `
+= labnode-one =================================== vESC =+
|Used CPU 100% Fail LOG 100%  Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50%  Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0%  Life SSD   0% Used BKP   0%|
+--------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK  SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +   influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +   mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +   mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +   ~            ~    ~  ~   ~ |
`
	displayCompactASCIISoloHost_59x10_2_3 = `
+= labnode-one ==================================== vESC =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
`
	displayCompactASCIISoloHost_60x10_3_3 = `
+= labnode-one ===================================== vESC =+
|Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%|
|Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%|
|Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%|
+----------------------------------------------------------+
|SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK|
|homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + |
|internet     0%   0%  -   +   mariadb    100% 100%  -   + |
|mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + |
|mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ |
`
	displayCompactASCIISoloHost_87x10 = `
+= labnode-one ================================================================ vESC =+
|Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%|
|Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%|
|Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%|
+-------------------------------------------------------------------------------------+
|SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK|
|homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + |
|internet              0%   0%  -   +            mariadb             100% 100%  -   + |
|mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + |
|mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_114x30_0_6 = `
+= labnode-one ================================== ^1/6 =++= labnode-two ================================== ^2/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%||Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%||Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%||Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------++-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK||SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + ||homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + ||internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + ||mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ ||mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-th~ ================================== ^3/6 =++= labnode-fo~ ================================== ^4/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%||Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%||Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%||Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------++-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK||SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + ||homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + ||internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + ||mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ ||mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-fi~ ================================== ^5/6 =++= labnode-six ================================== ^6/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%||Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%||Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%||Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------++-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK||SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + ||homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + ||internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + ||mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ ||mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_115x30_1_6 = `
+= labnode-one ================================== ^1/6 =+ += labnode-two ================================== ^2/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%| |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%| |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%| |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+ +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK| |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + | |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + | |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + | |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ | |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-th~ ================================== ^3/6 =+ += labnode-fo~ ================================== ^4/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%| |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%| |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%| |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+ +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK| |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + | |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + | |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + | |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ | |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-fi~ ================================== ^5/6 =+ += labnode-six ================================== ^6/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%| |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%| |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%| |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+ +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK| |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + | |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + | |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + | |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ | |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_116x30_2_6 = `
+= labnode-one ================================== ^1/6 =+  += labnode-two ================================== ^2/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|  |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|  |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|  |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+  +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|  |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |  |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |  |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |  |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |  |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-th~ ================================== ^3/6 =+  += labnode-fo~ ================================== ^4/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|  |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|  |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|  |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+  +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|  |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |  |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |  |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |  |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |  |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-fi~ ================================== ^5/6 =+  += labnode-six ================================== ^6/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|  |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|  |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|  |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+  +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|  |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |  |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |  |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |  |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |  |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_117x30_3_6 = `
+= labnode-one ================================== ^1/6 =+   += labnode-two ================================== ^2/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|   |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|   |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|   |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+   +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|   |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |   |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |   |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |   |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |   |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-th~ ================================== ^3/6 =+   += labnode-fo~ ================================== ^4/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|   |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|   |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|   |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+   +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|   |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |   |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |   |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |   |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |   |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
+= labnode-fi~ ================================== ^5/6 =+   += labnode-six ================================== ^6/6 =+
|Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|   |Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100%|
|Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|   |Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50%|
|Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|   |Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0%|
+-------------------------------------------------------+   +-------------------------------------------------------+
|SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|   |SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK|
|homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |   |homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   + |
|internet    0%   0%  -   +  mariadb   100% 100%  -   + |   |internet    0%   0%  -   +  mariadb   100% 100%  -   + |
|mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |   |mylongna~  50%  50%  -   +  mlflow      0%   0%  -   + |
|mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |   |mlserver  100% 100%  -   +  ~            ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_118x30_4_6 = `
+= labnode-one ==================================== ^1/6 =++= labnode-two ==================================== ^2/6 =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% || Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% || Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% || Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------++---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK || SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  || homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  || internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  || mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  || mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
+= labnode-th~ ==================================== ^3/6 =++= labnode-fo~ ==================================== ^4/6 =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% || Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% || Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% || Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------++---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK || SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  || homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  || internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  || mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  || mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
+= labnode-fi~ ==================================== ^5/6 =++= labnode-six ==================================== ^6/6 =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% || Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% || Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% || Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------++---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK || SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  || homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  || internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  || mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  || mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
`
	displayCompactASCIIMultiHost_119x30_5_6 = `
+= labnode-one ==================================== ^1/6 =+ += labnode-two ==================================== ^2/6 =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% | | Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% | | Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% | | Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------+ +---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK | | SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  | | homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  | | internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  | | mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  | | mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
+= labnode-th~ ==================================== ^3/6 =+ += labnode-fo~ ==================================== ^4/6 =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% | | Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% | | Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% | | Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------+ +---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK | | SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  | | homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  | | internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  | | mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  | | mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
+= labnode-fi~ ==================================== ^5/6 =+ += labnode-six ==================================== ^6/6 =+
| Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% | | Used CPU 100% Fail LOG 100% Warn TEM 100% Used SYS 100% |
| Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% | | Used RAM  50% Fail SHR  50% Revs Fan  50% Used SHR  50% |
| Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% | | Aloc RAM   0% Fail BCK   0% Life SSD   0% Used BKP   0% |
+---------------------------------------------------------+ +---------------------------------------------------------+
| SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK | | SERVICE    CPU  RAM BKP AOK SERVICE    CPU  RAM BKP AOK |
| homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  | | homeassi~ 100% 100%  -   +  influxdb3  50%  50%  -   +  |
| internet    0%   0%  -   +  mariadb   100% 100%  -   +  | | internet    0%   0%  -   +  mariadb   100% 100%  -   +  |
| mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  | | mylongna~  50%  50%  -   +  mlflow      0%   0%  -   +  |
| mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  | | mlserver  100% 100%  -   +  ~            ~    ~  ~   ~  |
`
	displayCompactASCIIMultiHost_120x30_6_6_Scales120x33 = `
+= labnode-one ===================================== ^1/6 =++= labnode-two ===================================== ^2/6 =+
|Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%||Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%|
|Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%||Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%|
|Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%||Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%|
+----------------------------------------------------------++----------------------------------------------------------+
|SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK||SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK|
|homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + ||homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + |
|internet     0%   0%  -   +   mariadb    100% 100%  -   + ||internet     0%   0%  -   +   mariadb    100% 100%  -   + |
|mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + ||mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + |
|mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ ||mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ |
+= labnode-th~ ===================================== ^3/6 =++= labnode-fo~ ===================================== ^4/6 =+
|Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%||Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%|
|Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%||Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%|
|Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%||Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%|
+----------------------------------------------------------++----------------------------------------------------------+
|SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK||SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK|
|homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + ||homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + |
|internet     0%   0%  -   +   mariadb    100% 100%  -   + ||internet     0%   0%  -   +   mariadb    100% 100%  -   + |
|mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + ||mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + |
|mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ ||mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ |
+= labnode-fi~ ===================================== ^5/6 =++= labnode-six ===================================== ^6/6 =+
|Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%||Used CPU 100%  Fail LOG 100%  Warn TEM 100%  Used SYS 100%|
|Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%||Used RAM  50%  Fail SHR  50%  Revs Fan  50%  Used SHR  50%|
|Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%||Aloc RAM   0%  Fail BCK   0%  Life SSD   0%  Used BKP   0%|
+----------------------------------------------------------++----------------------------------------------------------+
|SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK||SERVICE     CPU  RAM BKP AOK  SERVICE     CPU  RAM BKP AOK|
|homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + ||homeassis~ 100% 100%  -   +   influxdb3   50%  50%  -   + |
|internet     0%   0%  -   +   mariadb    100% 100%  -   + ||internet     0%   0%  -   +   mariadb    100% 100%  -   + |
|mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + ||mylongnam~  50%  50%  -   +   mlflow       0%   0%  -   + |
|mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ ||mlserver   100% 100%  -   +   ~             ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_128x30_Scales128x33 = `
+= labnode-one ======================================== ^1/6 =+  += labnode-two ======================================== ^2/6 =+
|Used CPU 100%   Fail LOG 100%   Warn TEM 100%   Used SYS 100%|  |Used CPU 100%   Fail LOG 100%   Warn TEM 100%   Used SYS 100%|
|Used RAM  50%   Fail SHR  50%   Revs Fan  50%   Used SHR  50%|  |Used RAM  50%   Fail SHR  50%   Revs Fan  50%   Used SHR  50%|
|Aloc RAM   0%   Fail BCK   0%   Life SSD   0%   Used BKP   0%|  |Aloc RAM   0%   Fail BCK   0%   Life SSD   0%   Used BKP   0%|
+-------------------------------------------------------------+  +-------------------------------------------------------------+
|SERVICE      CPU  RAM BKP AOK   SERVICE      CPU  RAM BKP AOK|  |SERVICE      CPU  RAM BKP AOK   SERVICE      CPU  RAM BKP AOK|
|homeassist~ 100% 100%  -   +    influxdb3    50%  50%  -   + |  |homeassist~ 100% 100%  -   +    influxdb3    50%  50%  -   + |
|internet      0%   0%  -   +    mariadb     100% 100%  -   + |  |internet      0%   0%  -   +    mariadb     100% 100%  -   + |
|mylongname~  50%  50%  -   +    mlflow        0%   0%  -   + |  |mylongname~  50%  50%  -   +    mlflow        0%   0%  -   + |
|mlserver    100% 100%  -   +    ~              ~    ~  ~   ~ |  |mlserver    100% 100%  -   +    ~              ~    ~  ~   ~ |
+= labnode-th~ ======================================== ^3/6 =+  += labnode-fo~ ======================================== ^4/6 =+
|Used CPU 100%   Fail LOG 100%   Warn TEM 100%   Used SYS 100%|  |Used CPU 100%   Fail LOG 100%   Warn TEM 100%   Used SYS 100%|
|Used RAM  50%   Fail SHR  50%   Revs Fan  50%   Used SHR  50%|  |Used RAM  50%   Fail SHR  50%   Revs Fan  50%   Used SHR  50%|
|Aloc RAM   0%   Fail BCK   0%   Life SSD   0%   Used BKP   0%|  |Aloc RAM   0%   Fail BCK   0%   Life SSD   0%   Used BKP   0%|
+-------------------------------------------------------------+  +-------------------------------------------------------------+
|SERVICE      CPU  RAM BKP AOK   SERVICE      CPU  RAM BKP AOK|  |SERVICE      CPU  RAM BKP AOK   SERVICE      CPU  RAM BKP AOK|
|homeassist~ 100% 100%  -   +    influxdb3    50%  50%  -   + |  |homeassist~ 100% 100%  -   +    influxdb3    50%  50%  -   + |
|internet      0%   0%  -   +    mariadb     100% 100%  -   + |  |internet      0%   0%  -   +    mariadb     100% 100%  -   + |
|mylongname~  50%  50%  -   +    mlflow        0%   0%  -   + |  |mylongname~  50%  50%  -   +    mlflow        0%   0%  -   + |
|mlserver    100% 100%  -   +    ~              ~    ~  ~   ~ |  |mlserver    100% 100%  -   +    ~              ~    ~  ~   ~ |
+= labnode-fi~ ======================================== ^5/6 =+  += labnode-six ======================================== ^6/6 =+
|Used CPU 100%   Fail LOG 100%   Warn TEM 100%   Used SYS 100%|  |Used CPU 100%   Fail LOG 100%   Warn TEM 100%   Used SYS 100%|
|Used RAM  50%   Fail SHR  50%   Revs Fan  50%   Used SHR  50%|  |Used RAM  50%   Fail SHR  50%   Revs Fan  50%   Used SHR  50%|
|Aloc RAM   0%   Fail BCK   0%   Life SSD   0%   Used BKP   0%|  |Aloc RAM   0%   Fail BCK   0%   Life SSD   0%   Used BKP   0%|
+-------------------------------------------------------------+  +-------------------------------------------------------------+
|SERVICE      CPU  RAM BKP AOK   SERVICE      CPU  RAM BKP AOK|  |SERVICE      CPU  RAM BKP AOK   SERVICE      CPU  RAM BKP AOK|
|homeassist~ 100% 100%  -   +    influxdb3    50%  50%  -   + |  |homeassist~ 100% 100%  -   +    influxdb3    50%  50%  -   + |
|internet      0%   0%  -   +    mariadb     100% 100%  -   + |  |internet      0%   0%  -   +    mariadb     100% 100%  -   + |
|mylongname~  50%  50%  -   +    mlflow        0%   0%  -   + |  |mylongname~  50%  50%  -   +    mlflow        0%   0%  -   + |
|mlserver    100% 100%  -   +    ~              ~    ~  ~   ~ |  |mlserver    100% 100%  -   +    ~              ~    ~  ~   ~ |
`
	displayCompactASCIIMultiHost_175x30 = `
+= labnode-one ================================================================ ^1/6 =+ += labnode-two ================================================================ ^2/6 =+
|Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%| |Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%|
|Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%| |Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%|
|Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%| |Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%|
+-------------------------------------------------------------------------------------+ +-------------------------------------------------------------------------------------+
|SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK| |SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK|
|homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + | |homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + |
|internet              0%   0%  -   +            mariadb             100% 100%  -   + | |internet              0%   0%  -   +            mariadb             100% 100%  -   + |
|mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + | |mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + |
|mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ | |mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ |
+= labnode-th~ ================================================================ ^3/6 =+ += labnode-fo~ ================================================================ ^4/6 =+
|Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%| |Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%|
|Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%| |Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%|
|Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%| |Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%|
+-------------------------------------------------------------------------------------+ +-------------------------------------------------------------------------------------+
|SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK| |SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK|
|homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + | |homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + |
|internet              0%   0%  -   +            mariadb             100% 100%  -   + | |internet              0%   0%  -   +            mariadb             100% 100%  -   + |
|mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + | |mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + |
|mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ | |mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ |
+= labnode-fi~ ================================================================ ^5/6 =+ += labnode-six ================================================================ ^6/6 =+
|Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%| |Used CPU 100%           Fail LOG 100%           Warn TEM 100%           Used SYS 100%|
|Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%| |Used RAM  50%           Fail SHR  50%           Revs Fan  50%           Used SHR  50%|
|Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%| |Aloc RAM   0%           Fail BCK   0%           Life SSD   0%           Used BKP   0%|
+-------------------------------------------------------------------------------------+ +-------------------------------------------------------------------------------------+
|SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK| |SERVICE              CPU  RAM BKP AOK           SERVICE              CPU  RAM BKP AOK|
|homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + | |homeassistant       100% 100%  -   +            influxdb3            50%  50%  -   + |
|internet              0%   0%  -   +            mariadb             100% 100%  -   + | |internet              0%   0%  -   +            mariadb             100% 100%  -   + |
|mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + | |mylongnamedservice   50%  50%  -   +            mlflow                0%   0%  -   + |
|mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ | |mlserver            100% 100%  -   +            ~                      ~    ~  ~   ~ |
`
	displayRelaxedASCIISoloHost_88x14_0_4_Scales120128x33 = `
+= labnode-one ================================================================= vESC =+
| Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% |
| Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% |
| Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% |
+--------------------------------------------------------------------------------------+
| SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME |
+--------------------------------------------------------------------------------------+
| homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d |
| influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d |
| internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d |
| mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d |
| mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d |
| mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d |
| mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d |
| ~                        ~             ~              ~    ~    ~    ~    ~        ~ |
`
	displayRelaxedUnicodeSoloHost_88x15_0_4 = `
╭─┐labnode-one┌─────────────────────────────────────────────────────────────────┐↓ESC┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯
`
	displayRelaxedUnicodeSoloHost_89x16_1_4 = `
╭─┐labnode-one┌──────────────────────────────────────────────────────────────────┐↓ESC┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯
`
	displayRelaxedUnicodeSoloHost_90x16_2_4 = `
╭─┐labnode-one┌───────────────────────────────────────────────────────────────────┐↓ESC┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯
`
	displayRelaxedUnicodeSoloHost_91x16_3_4_Scales287x55 = `
╭─┐labnode-one┌────────────────────────────────────────────────────────────────────┐↓ESC┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
`
	displayRelaxedUnicodeSoloHost_92x16_4_4 = `
╭─┐labnode-one┌─────────────────────────────────────────────────────────────────────┐↓ESC┌─╮
│ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% │
│ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% │
│ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~               ~                ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
`
	displayRelaxedASCIIMultiHost_176x45_0_8 = `
+= labnode-one ================================================================= ^1/6 =++= labnode-two ================================================================= ^2/6 =+
| Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% || Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% |
| Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% || Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% |
| Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% || Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% |
+--------------------------------------------------------------------------------------++--------------------------------------------------------------------------------------+
| SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME || SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME |
+--------------------------------------------------------------------------------------++--------------------------------------------------------------------------------------+
| homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d || homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d |
| influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d || influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d |
| internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d || internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d |
| mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d || mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d |
| mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d || mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d |
| mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d || mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d |
| mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d || mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d |
| ~                        ~             ~              ~    ~    ~    ~    ~        ~ || ~                        ~             ~              ~    ~    ~    ~    ~        ~ |
+= labnode-th~ ================================================================= ^3/6 =++= labnode-fo~ ================================================================= ^4/6 =+
| Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% || Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% |
| Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% || Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% |
| Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% || Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% |
+--------------------------------------------------------------------------------------++--------------------------------------------------------------------------------------+
| SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME || SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME |
+--------------------------------------------------------------------------------------++--------------------------------------------------------------------------------------+
| homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d || homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d |
| influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d || influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d |
| internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d || internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d |
| mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d || mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d |
| mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d || mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d |
| mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d || mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d |
| mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d || mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d |
| ~                        ~             ~              ~    ~    ~    ~    ~        ~ || ~                        ~             ~              ~    ~    ~    ~    ~        ~ |
+= labnode-fi~ ================================================================= ^5/6 =++= labnode-six ================================================================= ^6/6 =+
| Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% || Used CPU |||| 100%    Fail LOG |||| 100%    Warn TEM |||| 100%    Used SYS |||| 100% |
| Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% || Used RAM || |  50%    Fail SHR || |  50%    Revs Fan || |  50%    Used SHR || |  50% |
| Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% || Aloc RAM |  |   0%    Fail BCK |  |   0%    Life SSD |  |   0%    Used BKP |  |   0% |
+--------------------------------------------------------------------------------------++--------------------------------------------------------------------------------------+
| SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME || SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME |
+--------------------------------------------------------------------------------------++--------------------------------------------------------------------------------------+
| homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d || homeassistant  10.100.1001   |||||| 100%    |||||| 100%    -    +    +    0      23d |
| influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d || influxdb3      10.100.1002   |||  |  50%    |||  |  50%    -    +    +    0      46d |
| internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d || internet       10.100.1003   |    |   0%    |    |   0%    -    +    +    0      69d |
| mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d || mariadb        10.100.1004   |||||| 100%    |||||| 100%    -    +    +    0      92d |
| mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d || mylongnamedse~ 10.100.1005   |||  |  50%    |||  |  50%    -    +    +    0     115d |
| mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d || mlflow         10.100.1006   |    |   0%    |    |   0%    -    +    +    0     138d |
| mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d || mlserver       10.100.1007   |||||| 100%    |||||| 100%    -    +    +    0     162d |
| ~                        ~             ~              ~    ~    ~    ~    ~        ~ || ~                        ~             ~              ~    ~    ~    ~    ~        ~ |
`
	displayRelaxedUnicodeMultiHost_176x48_0_8 = `
╭─┐labnode-one┌─────────────────────────────────────────────────────────────────┐↑1/6┌─╮╭─┐labnode-two┌─────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% ││ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% ││ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% ││ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ ││ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌─────────────────────────────────────────────────────────────────┐↑3/6┌─╮╭─┐labnode-fo~┌─────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% ││ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% ││ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% ││ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ ││ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌─────────────────────────────────────────────────────────────────┐↑5/6┌─╮╭─┐labnode-six┌─────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% ││ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% ││ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% ││ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ ││ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯╰──────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_177x48_1_8 = `
╭─┐labnode-one┌─────────────────────────────────────────────────────────────────┐↑1/6┌─╮ ╭─┐labnode-two┌─────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │ │ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │ │ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │ │ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤ ├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │ │ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤ ├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │ │ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │ │ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │ │ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │ │ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │ │ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │ │ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │ │ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │ │ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯ ╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌─────────────────────────────────────────────────────────────────┐↑3/6┌─╮ ╭─┐labnode-fo~┌─────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │ │ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │ │ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │ │ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤ ├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │ │ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤ ├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │ │ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │ │ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │ │ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │ │ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │ │ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │ │ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │ │ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │ │ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯ ╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌─────────────────────────────────────────────────────────────────┐↑5/6┌─╮ ╭─┐labnode-six┌─────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │ │ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │ │ Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │ │ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────┤ ├──────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │ │ SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────┤ ├──────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │ │ homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │ │ influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │ │ internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │ │ mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │ │ mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │ │ mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │ │ mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │ │ ~                        ~             ~              ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────╯ ╰──────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_178x48_2_8 = `
╭─┐labnode-one┌──────────────────────────────────────────────────────────────────┐↑1/6┌─╮╭─┐labnode-two┌──────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% ││ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% ││ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% ││ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ ││ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯╰───────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌──────────────────────────────────────────────────────────────────┐↑3/6┌─╮╭─┐labnode-fo~┌──────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% ││ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% ││ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% ││ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ ││ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯╰───────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌──────────────────────────────────────────────────────────────────┐↑5/6┌─╮╭─┐labnode-six┌──────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% ││ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% ││ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% ││ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ ││ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯╰───────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_179x48_3_8 = `
╭─┐labnode-one┌──────────────────────────────────────────────────────────────────┐↑1/6┌─╮ ╭─┐labnode-two┌──────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │ │ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │ │ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │ │ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤ ├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │ │ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤ ├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │ │ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │ │ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │ │ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │ │ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │ │ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │ │ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │ │ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │ │ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯ ╰───────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌──────────────────────────────────────────────────────────────────┐↑3/6┌─╮ ╭─┐labnode-fo~┌──────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │ │ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │ │ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │ │ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤ ├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │ │ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤ ├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │ │ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │ │ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │ │ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │ │ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │ │ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │ │ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │ │ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │ │ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯ ╰───────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌──────────────────────────────────────────────────────────────────┐↑5/6┌─╮ ╭─┐labnode-six┌──────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │ │ Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100% │
│ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │ │ Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50% │
│ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │ │ Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0% │
├───────────────────────────────────────────────────────────────────────────────────────┤ ├───────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │ │ SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME │
├───────────────────────────────────────────────────────────────────────────────────────┤ ├───────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │ │ homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │ │ influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │ │ internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │ │ mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │ │ mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │ │ mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │ │ mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │ │ ~                        ~             ~               ~    ~    ~    ~    ~        ~ │
╰───────────────────────────────────────────────────────────────────────────────────────╯ ╰───────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_180x48_4_8 = `
╭─┐labnode-one┌───────────────────────────────────────────────────────────────────┐↑1/6┌─╮╭─┐labnode-two┌───────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  ││  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  ││  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  ││  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  ││  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  ││  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  ││  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  ││  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  ││  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  ││  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  ││  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  ││  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  ││  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌───────────────────────────────────────────────────────────────────┐↑3/6┌─╮╭─┐labnode-fo~┌───────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  ││  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  ││  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  ││  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  ││  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  ││  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  ││  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  ││  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  ││  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  ││  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  ││  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  ││  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  ││  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌───────────────────────────────────────────────────────────────────┐↑5/6┌─╮╭─┐labnode-six┌───────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  ││  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  ││  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  ││  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  ││  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  ││  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  ││  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  ││  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  ││  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  ││  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  ││  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  ││  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  ││  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_181x48_5_8 = `
╭─┐labnode-one┌───────────────────────────────────────────────────────────────────┐↑1/6┌─╮ ╭─┐labnode-two┌───────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │ │  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │ │  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤ ├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤ ├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │ │  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │ │  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │ │  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │ │  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │ │  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │ │  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │ │  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯ ╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌───────────────────────────────────────────────────────────────────┐↑3/6┌─╮ ╭─┐labnode-fo~┌───────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │ │  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │ │  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤ ├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤ ├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │ │  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │ │  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │ │  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │ │  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │ │  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │ │  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │ │  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯ ╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌───────────────────────────────────────────────────────────────────┐↑5/6┌─╮ ╭─┐labnode-six┌───────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%    Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │ │  Used RAM ■■■■  50%    Fail SHR ■■■■  50%    Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │ │  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%    Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├────────────────────────────────────────────────────────────────────────────────────────┤ ├────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERSION         CPU            MEM       BKP  HLT  CFG  RST  UPTIME  │
├────────────────────────────────────────────────────────────────────────────────────────┤ ├────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │ │  homeassistant  10.100.1001   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │ │  influxdb3      10.100.1002   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │ │  internet       10.100.1003   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │ │  mariadb        10.100.1004   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │ │  mylongnamedse~ 10.100.1005   ■■■■■■  50%    ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │ │  mlflow         10.100.1006   ■■■■■■   0%    ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │ │  mlserver       10.100.1007   ■■■■■■ 100%    ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~              ~    ~    ~    ~    ~        ~  │
╰────────────────────────────────────────────────────────────────────────────────────────╯ ╰────────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_182x48_6_8 = `
╭─┐labnode-one┌────────────────────────────────────────────────────────────────────┐↑1/6┌─╮╭─┐labnode-two┌────────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  ││  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  ││  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  ││  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  ││  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  ││  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  ││  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  ││  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  ││  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  ││  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  ││  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  ││  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  ││  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯╰─────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌────────────────────────────────────────────────────────────────────┐↑3/6┌─╮╭─┐labnode-fo~┌────────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  ││  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  ││  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  ││  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  ││  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  ││  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  ││  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  ││  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  ││  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  ││  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  ││  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  ││  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  ││  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯╰─────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌────────────────────────────────────────────────────────────────────┐↑5/6┌─╮╭─┐labnode-six┌────────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  ││  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  ││  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  ││  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  ││  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  ││  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  ││  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  ││  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  ││  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  ││  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  ││  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  ││  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  ││  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯╰─────────────────────────────────────────────────────────────────────────────────────────╯
	`
	displayRelaxedUnicodeMultiHost_183x48_7_8_Scales287x55 = `
╭─┐labnode-one┌────────────────────────────────────────────────────────────────────┐↑1/6┌─╮ ╭─┐labnode-two┌────────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │ │  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │ │  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │ │  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │ │  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │ │  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │ │  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │ │  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │ │  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │ │  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯ ╰─────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌────────────────────────────────────────────────────────────────────┐↑3/6┌─╮ ╭─┐labnode-fo~┌────────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │ │  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │ │  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │ │  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │ │  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │ │  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │ │  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │ │  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │ │  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │ │  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯ ╰─────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌────────────────────────────────────────────────────────────────────┐↑5/6┌─╮ ╭─┐labnode-six┌────────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │ │  Used CPU ■■■■ 100%    Fail LOG ■■■■ 100%     Warn TEM ■■■■ 100%    Used SYS ■■■■ 100%  │
│  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │ │  Used RAM ■■■■  50%    Fail SHR ■■■■  50%     Revs Fan ■■■■  50%    Used SHR ■■■■  50%  │
│  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │ │  Aloc RAM ■■■■   0%    Fail BCK ■■■■   0%     Life SSD ■■■■   0%    Used BKP ■■■■   0%  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │ │  SERVICE          VERSION         CPU             MEM       BKP  HLT  CFG  RST  UPTIME  │
├─────────────────────────────────────────────────────────────────────────────────────────┤ ├─────────────────────────────────────────────────────────────────────────────────────────┤
│  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │ │  homeassistant  10.100.1001   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      23d  │
│  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │ │  influxdb3      10.100.1002   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0      46d  │
│  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │ │  internet       10.100.1003   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0      69d  │
│  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │ │  mariadb        10.100.1004   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0      92d  │
│  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │ │  mylongnamedse~ 10.100.1005   ■■■■■■  50%     ■■■■■■  50%    ✖    ✔    ✔    0     115d  │
│  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │ │  mlflow         10.100.1006   ■■■■■■   0%     ■■■■■■   0%    ✖    ✔    ✔    0     138d  │
│  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │ │  mlserver       10.100.1007   ■■■■■■ 100%     ■■■■■■ 100%    ✖    ✔    ✔    0     162d  │
│  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │ │  ~                        ~             ~               ~    ~    ~    ~    ~        ~  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯ ╰─────────────────────────────────────────────────────────────────────────────────────────╯
`
	displayRelaxedUnicodeMultiHost_184x48_8_8 = `
╭─┐labnode-one┌─────────────────────────────────────────────────────────────────────┐↑1/6┌─╮╭─┐labnode-two┌─────────────────────────────────────────────────────────────────────┐↑2/6┌─╮
│ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% ││ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% │
│ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% ││ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% │
│ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% ││ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~               ~                ~    ~    ~    ~    ~        ~ ││ ~                        ~               ~                ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────────╯╰──────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-th~┌─────────────────────────────────────────────────────────────────────┐↑3/6┌─╮╭─┐labnode-fo~┌─────────────────────────────────────────────────────────────────────┐↑4/6┌─╮
│ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% ││ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% │
│ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% ││ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% │
│ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% ││ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~               ~                ~    ~    ~    ~    ~        ~ ││ ~                        ~               ~                ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────────╯╰──────────────────────────────────────────────────────────────────────────────────────────╯
╭─┐labnode-fi~┌─────────────────────────────────────────────────────────────────────┐↑5/6┌─╮╭─┐labnode-six┌─────────────────────────────────────────────────────────────────────┐↑6/6┌─╮
│ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% ││ Used CPU ■■■■■ 100%    Fail LOG ■■■■■ 100%    Warn TEM ■■■■■ 100%    Used SYS ■■■■■ 100% │
│ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% ││ Used RAM ■■■■■  50%    Fail SHR ■■■■■  50%    Revs Fan ■■■■■  50%    Used SHR ■■■■■  50% │
│ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% ││ Aloc RAM ■■■■■   0%    Fail BCK ■■■■■   0%    Life SSD ■■■■■   0%    Used BKP ■■■■■   0% │
├──────────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME ││ SERVICE          VERSION          CPU              MEM        BKP  HLT  CFG  RST  UPTIME │
├──────────────────────────────────────────────────────────────────────────────────────────┤├──────────────────────────────────────────────────────────────────────────────────────────┤
│ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d ││ homeassistant  10.100.1001   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      23d │
│ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d ││ influxdb3      10.100.1002   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0      46d │
│ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d ││ internet       10.100.1003   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0      69d │
│ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d ││ mariadb        10.100.1004   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0      92d │
│ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d ││ mylongnamedse~ 10.100.1005   ■■■■■■■■  50%    ■■■■■■■■  50%    ✖    ✔    ✔    0     115d │
│ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d ││ mlflow         10.100.1006   ■■■■■■■■   0%    ■■■■■■■■   0%    ✖    ✔    ✔    0     138d │
│ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d ││ mlserver       10.100.1007   ■■■■■■■■ 100%    ■■■■■■■■ 100%    ✖    ✔    ✔    0     162d │
│ ~                        ~               ~                ~    ~    ~    ~    ~        ~ ││ ~                        ~               ~                ~    ~    ~    ~    ~        ~ │
╰──────────────────────────────────────────────────────────────────────────────────────────╯╰──────────────────────────────────────────────────────────────────────────────────────────╯
`
)
