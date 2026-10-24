# Collapse CRMS hourly hydrographic rows to one row per station and day.
# Input columns (CIMS export): 1 Station ID, 2 Date, 5 Sensor Environment,
# 7 Adjusted Water Temperature (C), 11 Adjusted Salinity (ppt),
# 17 Adjusted Water Elevation to Datum (ft, NAVD88), 20 Geoid.
# Only hydrographic surface-water stations (IDs ending -H01, -H02, ...) are kept.
# The export is sorted by station and date, so rows are flushed on key change;
# step 2 re-aggregates any repeated keys by weighted mean.
BEGIN{FS=","; OFS=","; print "station,date,sal_sum,sal_n,wl_sum,wl_n,temp_sum,temp_n,hours,geoid"}
NR==1{next}
$1 !~ /-H[0-9][0-9]$/ {next}
$5 != "Surface Water" {next}
{
  k=$1 FS $2
  if(k!=prev && prev!=""){ flush() }
  prev=k; h++; g=$20
  if($11!=""){ss+=$11; sn++}
  if($17!=""){ws+=$17; wn++}
  if($7!=""){ts+=$7; tn++}
}
function flush(){ print prev, ss, sn, ws, wn, ts, tn, h, g; ss=sn=ws=wn=ts=tn=h=0; g="" }
END{ if(prev!="") flush() }
