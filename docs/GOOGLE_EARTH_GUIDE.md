# Google Earth guide

How to open `outputs/kmz/louisiana_coastal_wetlands.kmz`, explore it, compare historical imagery and record a screenshot or video.

Note: the KMZ was built and checked with Python (simplekml and lxml, including validation against the OGC KML 2.2 and Google gx schemas). It was not opened in Google Earth Pro or Google Earth Web when this repository was prepared. Open it yourself and follow the checks at the end before you share images from it.

## What is inside the KMZ

| Folder or item | Content |
|---|---|
| CWPPRA hydrologic basins (CPRA) | Basin outlines. Pontchartrain, Barataria and Terrebonne are drawn thicker; click a basin to see its land loss and gain totals |
| Persistent land change 1932 to 2015 | USGS SIM 3381 land change raster as a ground overlay (off by default; tick it to show). Dark red = loss 1932-1973, red = 1973-1990, orange = 1990-2015, green = land gain |
| CRMS hydro stations (analysed) | One sub-folder per group (Lake Maurepas, Pontchartrain, Barataria, Terrebonne key sites). Click a station for its statistics and salinity chart |
| USGS NWIS active sites | Triangles; the balloon lists what each site measures and links to its USGS page |
| Tour | A guided fly-through that opens each station balloon in turn |

The chart images are stored inside the KMZ, so the balloons work offline.

## Google Earth Pro (desktop, Windows or macOS)

1. Install Google Earth Pro from https://www.google.com/earth/about/versions/ (free).
2. File > Open, choose `louisiana_coastal_wetlands.kmz`. It appears under Temporary Places in the Places panel on the left.
3. To keep it between sessions, drag it into My Places, or right-click > Save to My Places.
4. Expand the folders and tick or untick layers. Double-click a station name to fly to it; click the icon to open its balloon.
5. Play the tour: expand the KMZ, double-click "Tour: Lake Maurepas to the Barataria and Terrebonne basins", then use the play controls at the lower left of the map. The tour opens and closes the station balloons by itself.
6. Show the land change overlay: tick "Persistent land change ...". Right-click it > Properties (Get Info on macOS) to change transparency with the slider.

### Historical imagery (Google Earth Pro only)

1. View > Historical Imagery, or click the clock icon in the toolbar.
2. A time slider appears at the top left of the map. Drag it to step through the dated aerial and satellite images Google holds for the view.
3. Good places to compare:
   * the Lake Maurepas shoreline and the swamp along the Amite and Tickfaw rivers (look for open water in former swamp);
   * the marsh between Lake Salvador and Barataria Bay;
   * lower Terrebonne Parish around Isle de Jean Charles and Lake Boudreaux, where land loss is widespread.
4. Turn the land change overlay on and off while the slider is at an older date to see whether the mapped loss matches what the imagery shows.
5. Imagery dates differ by location and some years are missing; the slider only shows dates available for the current view.

### Screenshot

* File > Save > Save Image. Use the Map Options button in that toolbar to add a title, a legend and a scale, and choose a resolution (up to "Maximum").
* Close balloons and hide the sidebar (View > Sidebar) first for a clean frame.

### Video of the tour

1. Tools > Movie Maker.
2. Under "Record from", choose "A saved tour" and pick the tour from this KMZ.
3. Choose the size (for example 1920 x 1080), frames per second (30) and a file name and folder. MP4 (H.264) plays everywhere.
4. Click "Create Movie". Rendering takes several minutes; balloons opened by the tour are included.
5. Alternative: Tools > Record a Tour (the camcorder icon) records your own live navigation, which you can then save and export with Movie Maker.

## Google Earth Web (browser)

1. Go to https://earth.google.com/web/ (Chrome, Edge or Firefox).
2. Open the Projects panel (the bookmark icon on the left) > New project > Import KML file from computer > choose the KMZ.
   * Older menus: Projects > Open > Import KML file from computer.
3. The folders appear in the project. Click a station to open its balloon.
4. Limitations in Google Earth Web:
   * gx:Tour playback support is limited; if the tour does not play, use Google Earth Pro for the tour and the video.
   * Historical imagery: the web version has a time-lapse layer (Layers > Timelapse in some releases) but not the full historical imagery slider of Google Earth Pro.
   * Balloon HTML may be simplified, and large ground overlays may draw slowly.
5. Screenshot: use the camera icon ("Capture") in the left toolbar, or your operating system's screenshot tool.
6. Video: the "Create a story or presentation" tools in Projects can play a sequence of saved views; record them with a screen recorder (for example the macOS Screenshot toolbar with Shift-Command-5, or the Xbox Game Bar on Windows with Win-Alt-R).

## Checks to make when you first open the file

* All station icons fall on the marsh or water at the expected places (Lake Maurepas stations around the lake, Barataria and Terrebonne stations south of New Orleans and Houma).
* Each station balloon shows a chart and a statistics table.
* The basin outlines match the CPRA basin map, and the land change overlay lines up with the coast (no shift of more than a pixel or two, about 90 m).
* The tour plays from the coast overview to Lake Maurepas and then south through the key sites.

## Opening the same layers in ArcGIS Pro or QGIS

* QGIS: Layer > Add Layer > Add Vector Layer, choose the KMZ (GDAL LIBKML driver) or the GeoJSON files in `data/`.
* ArcGIS Pro: Analysis > Tools > "KML To Layer" converts the KMZ to a file geodatabase and layer. These steps were not run for this repository.
