'use strict';
// Presentation only: never round values used by the scanner or its financial filters.
const Money = (() => {
 const numeric = value => typeof value === 'number' && Number.isFinite(value);
 const group = (value, digits=0) => new Intl.NumberFormat('it-IT', {
  minimumFractionDigits:0, maximumFractionDigits:digits, useGrouping:'always'
 }).format(value);
 function formatCompact(value) {
  if (!numeric(value)) return 'Non disponibile';
  const abs=Math.abs(value);
  if (abs>=1e9) return group(value/1e9,2)+' Mld $';
  if (abs>=1e6) return group(value/1e6,2)+' Mln $';
  if (abs>=1e5) return group(value/1e3,1)+' mila $';
  if (abs>=1e3) return group(value,0)+' $';
  return group(value,abs>0&&abs<1?4:2)+' $';
 }
 function formatExact(value) {
  return numeric(value)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(value):'Non disponibile';
 }
 return {formatCompact,formatExact};
})();
if(typeof module!=='undefined')module.exports=Money;
