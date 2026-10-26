const {test}=require('node:test'),assert=require('node:assert/strict');
const Money=require('../docs/money.js');
test('Italian compact labels distinguish thousands, millions and billions',()=>{
 assert.equal(Money.formatCompact(4434000),'4,43 Mln $');
 assert.equal(Money.formatCompact(4434000000),'4,43 Mld $');
 assert.equal(Money.formatCompact(443400),'443,4 mila $');
 assert.equal(Money.formatCompact(1200),'1.200 $');
 assert.equal(Money.formatCompact(0),'0 $');
 assert.equal(Money.formatCompact(-1540000),'-1,54 Mln $');
});
test('missing values never become zero or a fabricated amount',()=>{
 for(const x of [null,undefined,NaN,Infinity,'4434000'])
  assert.equal(Money.formatCompact(x),'Non disponibile');
});
test('full amounts are available for interactive reveal without changing backend numbers',()=>{
 assert.match(Money.formatExact(4434000),/4.434.000/);
 assert.equal(Money.formatExact(null),'Non disponibile');
});
