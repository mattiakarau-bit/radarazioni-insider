'use strict';
/* Local-only user supplied market observations. NOT a quote feed, financial
 * certification, or public dataset. Never calls APIs or sends user data. */
const PersonalMarket=(()=>{
 const positive=n=>typeof n==='number'&&Number.isFinite(n)&&n>0;
 const day=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(Date.parse(s+'T00:00:00Z'))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
 const safeSource=s=>{try{const u=new URL(s);return u.protocol==='https:'&&!u.username&&!u.password&&!!u.hostname;}catch{return false}};
 function validate(raw,today=new Date().toISOString().slice(0,10)){
  if(!day(today))throw Error('Data di riferimento non valida');
  const ticker=String(raw.ticker||'').trim().toUpperCase();
  const date=String(raw.date||'').trim();
  const price=Number(raw.price);
  const source_url=String(raw.source_url||'').trim();
  const class_verified=raw.class_verified===true||String(raw.class_verified).trim().toLowerCase()==='si'||String(raw.class_verified).trim().toLowerCase()==='yes';
  if(!/^[A-Z][A-Z0-9.-]{0,13}$/.test(ticker))throw Error('Ticker assente o non valido');
  if(!positive(price)||price>1e7)throw Error('Prezzo USD assente o non valido');
  if(!day(date)||date>today)throw Error('Data prezzo non valida o futura');
  if(!safeSource(source_url))throw Error('Inserisci una pagina HTTPS della fonte prezzo');
  if(raw.currency&&String(raw.currency).trim().toUpperCase()!=='USD')throw Error('Sono supportati soltanto prezzi in USD');
  const market_cap=raw.market_cap===''||raw.market_cap==null?null:Number(raw.market_cap);
  const historical_cap=raw.historical_cap===''||raw.historical_cap==null?null:Number(raw.historical_cap);
  if(market_cap!==null&&!positive(market_cap))throw Error('Capitalizzazione attuale non valida');
  if(historical_cap!==null&&!positive(historical_cap))throw Error('Capitalizzazione storica non valida');
  const market_cap_date=market_cap===null?null:String(raw.market_cap_date||'').trim();
  const historical_cap_date=historical_cap===null?null:String(raw.historical_cap_date||'').trim();
  if(market_cap!==null&&(!day(market_cap_date)||market_cap_date>today))throw Error('Serve la data della capitalizzazione attuale');
  if(historical_cap!==null&&(!day(historical_cap_date)||historical_cap_date>today))throw Error('Serve la data della capitalizzazione storica');
  return {ticker,price,date,source_url,class_verified,market_cap,market_cap_date,historical_cap,historical_cap_date};
 }
 function csvCells(line){
  const cells=[];let acc='',quoted=false;
  for(let i=0;i<line.length;i++){
   const c=line[i];
   if(c==='"'){if(quoted&&line[i+1]==='"'){acc+='"';i++}else quoted=!quoted}
   else if(c===','&&!quoted){cells.push(acc.trim());acc=''}
   else acc+=c;
  }
  if(quoted)throw Error('Virgolette CSV non chiuse');
  cells.push(acc.trim());return cells;
 }
 const columns=['ticker','price','date','source_url','class_verified','market_cap','market_cap_date','historical_cap','historical_cap_date'];
 function parseCSV(input,today){
  if(typeof input!=='string'||input.length>300000)throw Error('File CSV non valido o troppo grande (massimo 300 KB)');
  const lines=input.replace(/^\uFEFF/,'').split(/\r?\n/).filter(x=>x.trim()&&!x.trim().startsWith('#'));
  if(lines.length<2||lines.length>151)throw Error('Servono una intestazione e da 1 a 150 righe');
  const header=csvCells(lines[0]);for(const key of ['ticker','price','date','source_url'])if(!header.includes(key))throw Error('Colonna CSV mancante: '+key);
  const result={};for(let i=1;i<lines.length;i++){
   const values=csvCells(lines[i]);if(values.length!==header.length)throw Error('Riga '+(i+1)+': numero colonne diverso');
   const obj=Object.fromEntries(header.map((h,j)=>[h,values[j]]));
   let row;try{row=validate(obj,today)}catch(e){throw Error('Riga '+(i+1)+': '+e.message)}
   if(Object.hasOwn(result,row.ticker))throw Error('Ticker duplicato nel file: '+row.ticker);
   result[row.ticker]=row;
  }
  return result;
 }
 function age(date,today){if(!day(date)||!day(today))return Infinity;return Math.round((Date.parse(today)-Date.parse(date))/86400000)}
 function assess(company,quote,today=new Date().toISOString().slice(0,10)){
  if(!company||!quote)return null;
  const valid=validate(quote,today);
  if(String(company.symbol||'').toUpperCase()!==valid.ticker)return null;
  const lastCloseFresh=age(valid.date,today)>=0&&age(valid.date,today)<=10;
  const insider=company.weighted_price;
  const comparable=lastCloseFresh&&valid.class_verified&&positive(insider)&&company.aggregation_verified===true&&!company.amount_review_required;
  const distance_pct=comparable?Number(((valid.price/insider-1)*100).toFixed(2)):null;
  const nearby=distance_pct===null?null:Math.abs(distance_pct)<=15;
  const currentCapFresh=valid.market_cap!==null&&age(valid.market_cap_date,today)>=0&&age(valid.market_cap_date,today)<=10;
  const histCapNear=valid.historical_cap!==null&&day(company.window_start)&&day(company.window_end)&&valid.historical_cap_date>=company.window_start&&valid.historical_cap_date<=company.window_end;
  const required_amount=histCapNear?Math.max(100000,Math.min(2000000,valid.historical_cap*0.00002)):null;
  const current_cap_pass=currentCapFresh?valid.market_cap>=500000000:null;
  const weekly_pass=required_amount===null?null:company.amount>=required_amount;
  return {quote:valid,price_fresh:lastCloseFresh,distance_pct,nearby,
          current_cap_pass,required_amount,weekly_pass,
          historical_cap_usable:histCapNear,current_cap_usable:currentCapFresh,
          preliminary_only:true,complete_investment_review:false};
 }
 const template=columns.join(',')+'\n'+'UBER,,,,,,,,\n';
 return {columns,template,validate,parseCSV,assess};
})();
if(typeof module!=='undefined')module.exports=PersonalMarket;
