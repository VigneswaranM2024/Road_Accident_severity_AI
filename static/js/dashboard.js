// Dashboard JS: fetch /dashboard-data and render charts and model perf
window.addEventListener('DOMContentLoaded', ()=>{
  fetch('/dashboard-data').then(r=>r.json()).then(data=>{
    try{
      const speedData = data.speed_vs_severity; // {bucket: {Low: n, Medium: n, High: n}}
      const labels = Object.keys(speedData);
      const low = labels.map(l=>speedData[l]['Low']||0);
      const med = labels.map(l=>speedData[l]['Medium']||0);
      const high = labels.map(l=>speedData[l]['High']||0);
      // Speed chart stacked
      const ctx = document.getElementById('speedChart').getContext('2d');
  new Chart(ctx, {type:'bar', data:{labels, datasets:[{label:'Low',data:low, backgroundColor:'#28a745'},{label:'Medium',data:med, backgroundColor:'#ffc107'},{label:'High',data:high, backgroundColor:'#dc3545'}]}, options:{responsive:true, scales:{x:{stacked:true}, y:{stacked:true}}}});

      // Weather vs severity: aggregate into counts per weather
      const weatherObj = data.weather_vs_severity || {};
      const wLabels = Object.keys(weatherObj).slice(0,8); // top 8
      const wLow = wLabels.map(w=>weatherObj[w]['Low']||0);
      const wMed = wLabels.map(w=>weatherObj[w]['Medium']||0);
      const wHigh = wLabels.map(w=>weatherObj[w]['High']||0);
      const wctx = document.getElementById('weatherChart').getContext('2d');
  new Chart(wctx, {type:'bar', data:{labels:wLabels, datasets:[{label:'Low',data:wLow, backgroundColor:'#28a745'},{label:'Medium',data:wMed, backgroundColor:'#ffc107'},{label:'High',data:wHigh, backgroundColor:'#dc3545'}]}, options:{responsive:true, scales:{x:{stacked:true}, y:{stacked:true}}}});

      // Model perf
      const perf = data.model_perf_summary || {};
      if (perf.decision_tree){
        document.getElementById('dt-acc').textContent = (perf.decision_tree.accuracy||0).toFixed(3);
        const dtcm = perf.decision_tree.cm || '/static/images/confusion_matrix_dt.png';
        document.getElementById('cm-dt').src = '/' + dtcm.replace(/^\//,'');
      }
      if (perf.random_forest){
        document.getElementById('rf-acc').textContent = (perf.random_forest.accuracy||0).toFixed(3);
        const rfcm = perf.random_forest.cm || '/static/images/confusion_matrix_rf.png';
        document.getElementById('cm-rf').src = '/' + rfcm.replace(/^\//,'');
      }

      // Highlights: small summary
      const highlights = document.getElementById('dashboard-highlights');
      highlights.innerHTML = '';
      const totalPreds = (function(){
        // sum speed counts
        let s=0; labels.forEach(l=>{ s += (speedData[l]['Low']||0) + (speedData[l]['Medium']||0) + (speedData[l]['High']||0); });
        return s;
      })();
      const li1 = document.createElement('li'); li1.className='list-group-item'; li1.textContent = `Total recent records: ${totalPreds}`; highlights.appendChild(li1);
      const topWeather = wLabels[0] || 'N/A';
      const li2 = document.createElement('li'); li2.className='list-group-item'; li2.textContent = `Top weather seen: ${topWeather}`; highlights.appendChild(li2);

    }catch(err){
      console.error('Dashboard render error', err);
    }
  }).catch(err=>{ console.error('Dashboard data fetch failed', err); });
});
