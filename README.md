# DaWanda exporter

Export-Programm für ein Dawanda-Nutzerprofil. Es benötigt [Python](http://python.org) in Version 3.6 (oder höher).

Beim ersten Aufruf werden ggf. benötigte Abhängigkeiten installiert (siehe `requirements.txt`).
Es werden die Zugangsdaten für DaWanda abgefragt und der Datendownload beginnt, dabei wird ein Fortschritt angezeigt.

```
$ python3 dawanda.py 
DaWanda username: youngage
DaWanda password (not shown): 
[*] output: dawanda_2018-08-11_11-44-30.zip
[*] fetching profile ... youngage
[*] fetching ratings
    got 107
[*] fetching products
    got 711
[*] Logging out.[+] done [711 products] [107 ratings]
```

Das Ergebnis ist eine ZIP-Datei mit mehreren JSON-Dateien sowie allen Produktbildern in einem Unterordner:
```
Archive:  dawanda_2018-08-11_11-44-30.zip
Zip file size: 7169920283 bytes, number of entries: 1630
?rw-------  2.0 unx     1198 b- defN 18-Aug-11 11:44 profile.json
?rw-------  2.0 unx   134380 b- defN 18-Aug-11 11:44 productlist.json
?rw-------  2.0 unx  5772448 b- defN 18-Aug-11 12:01 products.json
?rw-------  2.0 unx  5342758 b- stor 80-Jan-01 00:00 product_images/123456789.jpeg
...
?rw-------  2.0 unx   192375 b- stor 80-Jan-01 00:00 product_images/234567890.jpeg
-rw-------  3.0 unx    21031 tx defN 18-Aug-11 12:54 ratings.json
1630 files, 7175253081 bytes uncompressed, 7169687659 bytes compressed:  0.1%
```
