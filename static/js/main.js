// Frontend logic: form handling, fetch to /predict, weather detect, Chart.js, and voice alerts
let lastPrediction = null;
let isAlertPlaying = false;
let alertInterval = null;
let alertTimeout = null;
let map = null;
let marker = null;
let socket = null;

function initMap() {
    map = L.map('riskMap').setView([20.5937, 78.9629], 5); // Default India
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);
}

function updateMap(city, severity_percent, severity_label) {
    if (!city || !map) return;
    fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(city)}`)
    .then(r => r.json())
    .then(data => {
        if (data && data.length > 0) {
            const lat = data[0].lat;
            const lon = data[0].lon;
            map.flyTo([lat, lon], 12);
            if (marker) map.removeLayer(marker);
            
            let color = severity_label === 'High' ? '#ef4444' : severity_label === 'Medium' ? '#f59e0b' : '#10b981';
            marker = L.circleMarker([lat, lon], {
                radius: 15,
                fillColor: color,
                color: "#fff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            marker.bindPopup(`<b style="color:black">${city}</b><br><span style="color:black">Risk: ${severity_label} (${severity_percent.toFixed(0)}%)</span>`).openPopup();
        }
    }).catch(e => console.error("Geocoding failed", e));
}

function initSocket() {
    socket = io();
    socket.on('new_prediction', function(j) {
        // Append to admin list globally
        const lp = document.getElementById('last-preds');
        const li = document.createElement('li'); 
        li.className='list-group-item'; 
        let badgeClass = j.severity_label === 'High' ? 'bg-danger' : j.severity_label === 'Medium' ? 'bg-warning text-dark' : 'bg-success';
        
        let timeLabel = j.timestamp ? new Date(j.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        li.innerHTML = `<span style="opacity:0.7">${timeLabel}</span> - <b>${j.city || 'Unknown'}</b> - <span class="badge ${badgeClass}">${j.severity_label} ${j.severity_percent.toFixed(0)}%</span>`;
        lp.prepend(li);
        
        // Update map for global live incoming threats
        updateMap(j.city, j.severity_percent, j.severity_label);
    });
}

// Animated toast-like alert used for in-car style warnings
function showAlert(message, level){
  const alertBox = document.getElementById('alertBox');
  if (!alertBox) return;
  alertBox.className = `alert-box show ${level}`;
  alertBox.textContent = message;
  // hide after 5s
  setTimeout(()=>{ alertBox.classList.remove('show'); }, 5000);
}

function updateSeverityUI(percent, label){
  const bar = document.getElementById('severity-bar');
  bar.style.width = percent + '%';
  bar.textContent = percent.toFixed(0) + '%';
  const badge = document.getElementById('severity-badge');
  badge.textContent = label;
  badge.className = 'badge ' + (label==='High' ? 'bg-danger' : label==='Medium' ? 'bg-warning text-dark' : 'bg-success');
}

function startAlertVoice(){
  if (isAlertPlaying) return;
  if (document.getElementById('mute_alert').checked) return;
  const message = '⚠️ Warning! Warning! High accident risk detected! Please slow down immediately!';
  const utter = new SpeechSynthesisUtterance(message);
  utter.rate = 1;
  utter.pitch = 1;
  utter.volume = 0.9;

  isAlertPlaying = true;
  // Speak immediately
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
  // Repeat every 1500ms until 5s total
  let start = Date.now();
  alertInterval = setInterval(()=>{
    if (Date.now() - start >= 5000){
      stopAlertVoice();
      return;
    }
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
  }, 1500);
  // Safety timeout
  alertTimeout = setTimeout(()=>{ stopAlertVoice(); }, 5200);
}

function stopAlertVoice(){
  if (!isAlertPlaying) return;
  window.speechSynthesis.cancel();
  if (alertInterval) clearInterval(alertInterval);
  if (alertTimeout) clearTimeout(alertTimeout);
  alertInterval = null; alertTimeout = null; isAlertPlaying = false;
}

async function doPredict(){
  const btn = document.getElementById('predict-btn');
  btn.disabled = true;
  const payload = {
    speed: document.getElementById('speed').value,
    road_type: document.getElementById('road_type').value,
    vehicle_type: document.getElementById('vehicle_type').value,
    surface: document.getElementById('surface').value,
    time_of_day: document.getElementById('time_of_day').value,
    weather_mode: document.getElementById('auto_mode').checked ? 'auto' : 'manual',
    manual_weather: document.getElementById('manual_weather').value,
    city_name: document.getElementById('city_name').value
    ,mute_alert: document.getElementById('mute_alert').checked
  };
  try{
    const res = await fetch('/predict', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    const j = await res.json();
    if (j.error){
      alert('Error: ' + j.error);
    } else {
      lastPrediction = j;
      updateSeverityUI(j.severity_percent, j.severity_label);
      document.getElementById('advice-box').textContent = j.advice_text;
      document.getElementById('detected-weather').textContent = j.detected_weather;
      if (j.shap_explanation) {
          document.getElementById('shap-box').innerHTML = j.shap_explanation;
      }
      // Show color-coded Bootstrap alert in the prediction area
      const alertDiv = document.getElementById('predictionAlert');
      if (alertDiv){
        alertDiv.className = 'alert mt-3 text-center';
        if (j.severity_label === 'High') {
          alertDiv.classList.add('alert-danger');
          alertDiv.textContent = 'High risk — take immediate action';
        } else if (j.severity_label === 'Medium') {
          alertDiv.classList.add('alert-warning');
          alertDiv.textContent = 'Moderate risk — drive cautiously';
        } else {
          alertDiv.classList.add('alert-success');
          alertDiv.textContent = 'Low risk — maintain safe speed';
        }
        alertDiv.style.display = 'block';
        alertDiv.style.opacity = '0';
        setTimeout(()=>{ alertDiv.style.opacity = '1'; }, 50);
      }
      // Save last to localStorage for download
      localStorage.setItem('lastPrediction', JSON.stringify(j));
      // DOM append for historical list and Map Update is handled by Socket.IO 'new_prediction' event
      
      // Show animated alert popup
      const pMsg = j.severity_label === 'High' ? '⚠️ Warning! Dangerous conditions detected. Please slow down immediately.' : j.severity_label === 'Medium' ? 'Drive carefully. Road might be slippery.' : 'All clear. Maintain safe speed.';
      const pLevel = j.severity_label === 'High' ? 'danger' : j.severity_label === 'Medium' ? 'warning' : 'success';
      showAlert(pMsg, pLevel);
      if (j.severity_percent >= 85){
        startAlertVoice();
      } else {
        stopAlertVoice();
      }
    }
  } catch(err){
    alert('Request failed: ' + err);
  } finally {
    btn.disabled = false;
  }
}

async function detectWeather(){
  const city = document.getElementById('city_name').value;
  if (!city) { alert('Enter city'); return; }
  try{
    const res = await fetch('/detect-weather?city=' + encodeURIComponent(city));
    const j = await res.json();
    if (j.error){ alert('Detect failed: '+(typeof j.error ==='object'? JSON.stringify(j.error):j.error)); }
    else {
      // Update manual weather selection hidden
      const mw = document.getElementById('manual_weather');
      mw.value = j.mapped || j.mapped || mw.value;
      document.getElementById('detected-weather').textContent =`${j.mapped || j.main || "Unknown"} | ${j.temp ? j.temp + "C":""}`;
      alert('Detected weather: ' + (j.mapped || j.main));
    }
  } catch(e){ alert('Detect error: '+e); }
}

function setup(){
  initMap();
  initSocket();
  // Hook predict and other buttons
  document.getElementById('predict-btn').addEventListener('click', doPredict);
  document.getElementById('detect-weather').addEventListener('click', detectWeather);
  document.getElementById('download-last').addEventListener('click', ()=>{
    const txt = localStorage.getItem('lastPrediction');
    if (!txt){ alert('No last prediction'); return; }
    const blob = new Blob([txt], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'last_prediction.json'; a.click(); URL.revokeObjectURL(url);
  });

  // Weather mode toggles
  document.getElementById('manual_mode').addEventListener('change', ()=>{
    document.getElementById('manual-weather-group').style.display='block';
    document.getElementById('city-group').style.display='none';
  });
  document.getElementById('auto_mode').addEventListener('change', ()=>{
    document.getElementById('manual-weather-group').style.display='none';
    document.getElementById('city-group').style.display='block';
  });

  // Form validation: disable predict button until required fields (time_of_day, speed) present
  function validateForm(){
    let formValid = true;
    const timeOfDay = document.getElementById('time_of_day') ? document.getElementById('time_of_day').value : '';
    const speed = document.getElementById('speed') ? document.getElementById('speed').value : '';
    if (!timeOfDay) { formValid = false; }
    if (!speed) { formValid = false; }
    document.getElementById('predict-btn').disabled = !formValid;
    return formValid;
  }

  // Disable predict initially until validation passes
  document.getElementById('predict-btn').disabled = true;

  // Attach listeners to revalidate on user input
  const inputsToWatch = ['time_of_day','speed','road_type','vehicle_type','surface','manual_weather'];
  inputsToWatch.forEach(id=>{
    const el = document.getElementById(id);
    if (!el) return;
    const ev = (el.tagName.toLowerCase()==='select' || el.type==='checkbox' || el.type==='radio') ? 'change' : 'input';
    el.addEventListener(ev, validateForm);
  });

  // Run initial validation in case of prefilled values
  validateForm();

  // Render chart
  const ctx = document.getElementById('monthlyChart').getContext('2d');
  fetch('/monthly-trends').then(r=>r.json()).then(data=>{
    const labels = Object.keys(data);
    const vals = Object.values(data);
    new Chart(ctx, {type:'bar', data:{labels, datasets:[{label:'Accidents',data:vals, backgroundColor:'#4e73df'}]}});
  });
}

window.addEventListener('DOMContentLoaded', setup);
