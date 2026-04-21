document.addEventListener("DOMContentLoaded", () => {
  // Load data embedded from backend
  const dataScript = document.getElementById("reportsData");
  let reportsData = { distribution: {}, history: [], trusted_contact: null, current_days: 1 };
  
  try {
    if (dataScript) {
      reportsData = JSON.parse(dataScript.textContent);
    }
  } catch (e) {
    console.error("Failed to parse reports data", e);
  }


  // Pre-fill Trusted Contact
  if (reportsData.trusted_contact) {
    document.getElementById("trustedEmail").value = reportsData.trusted_contact;
  }

  const { distribution, history, calendar_history, current_days } = reportsData;

  // 1. Time Filter Handling
  const filterPills = document.querySelectorAll(".filter-pill");
  filterPills.forEach(pill => {
    if (parseInt(pill.dataset.days) === current_days) {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
    }

    pill.addEventListener("click", () => {
      // Direct reload to backend endpoint with new params to fetch new scoped data
      const days = pill.dataset.days;
      window.location.href = `/reports?days=${days}`;
    });
  });

  // Mood configuration setup
  const MOOD_COLORS = {
    Awesome: "#86efac",
    Good: "#bbf7d0",
    Fine: "#fef08a",
    Bad: "#fed7aa",
    Terrible: "#fca5a5"
  };
  const MOOD_SCORES = {
    Awesome: 5,
    Good: 4,
    Fine: 3,
    Bad: 2,
    Terrible: 1
  };

  // 2. Charts Initialization
  initPieChart(distribution, MOOD_COLORS);
  initLineChart(history, MOOD_SCORES, MOOD_COLORS);

  // 3. Calendar View logic
  window.currentMonthOffset = 0;
  initCalendar(calendar_history);

  const prevBtn = document.getElementById("prevMonthBtn");
  const nextBtn = document.getElementById("nextMonthBtn");
  if (prevBtn && nextBtn) {
    // Add text if icons are missing
    if (!prevBtn.innerHTML) prevBtn.innerHTML = "‹";
    if (!nextBtn.innerHTML) nextBtn.innerHTML = "›";

    prevBtn.addEventListener("click", () => {
      window.currentMonthOffset -= 1;
      initCalendar(calendar_history);
    });
    nextBtn.addEventListener("click", () => {
      window.currentMonthOffset += 1;
      initCalendar(calendar_history);
    });
  }


  // 4. Emotional Insights
  generateInsights(distribution, history);

  // 5. Trusted Contact API
  const contactForm = document.getElementById("trustedContactForm");
  contactForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const emailStr = document.getElementById("trustedEmail").value.trim();
    if (!emailStr) return;

    try {
      const res = await fetch("/api/trusted_contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailStr }),
      });
      const data = await res.json();
      const fb = document.getElementById("trustedFeedback");
      if (data.ok) {
        fb.textContent = "Trusted contact saved successfully ";
        fb.style.color = "var(--success-color)";
      } else {
        fb.textContent = "Failed: " + data.error;
        fb.style.color = "var(--error-color)";
      }
    } catch (err) {
      console.error(err);
    }
  });
});

function initPieChart(distribution, colorsObj) {
  const ctx = document.getElementById('moodPieChart');
  if (!ctx) return;

  const labels = Object.keys(distribution);
  const data = Object.values(distribution);

  const total = data.reduce((a, b) => a + b, 0);

  if (total === 0) {
    document.getElementById('pieInsightText').textContent = "No entries yet.";
  } else {
    // Find highest
    const maxVal = Math.max(...data);
    const maxLabel = labels[data.indexOf(maxVal)];
    const pct = Math.round((maxVal / total) * 100);
    document.getElementById('pieInsightText').textContent = `You felt '${maxLabel}' ${pct}% of the time!`;
  }

  const bgColors = labels.map(l => colorsObj[l] || "#cbd5e1");

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: bgColors,
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      cutout: '65%',
      plugins: {
        legend: { position: 'bottom' }
      }
    }
  });
}

function initLineChart(history, scoreMap, colorMap) {
  const ctx = document.getElementById('moodLineChart');
  if (!ctx) return;

  // We want to map dates to scores. For multiple entries in a day, take average or just list them.
  // Simplifying: Just plot each entry linearly against its CreatedAt date format
  const labels = history.map(item => new Date(item.created_at).toLocaleDateString(undefined, {month: 'short', day:'numeric'}));
  const dataPoints = history.map(item => scoreMap[item.selected_mood] || 3);

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Mood Level',
        data: dataPoints,
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        borderWidth: 3,
        pointBackgroundColor: history.map(item => colorMap[item.selected_mood] || '#10b981'),
        pointRadius: 5,
        fill: true,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          min: 0,
          max: 6,
          ticks: {
            stepSize: 1,
            callback: function(value) {
              const reverseMap = {1:'Terrible', 2:'Bad', 3:'Fine', 4:'Good', 5:'Awesome'};
              return reverseMap[value] || '';
            }
          }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function initCalendar(history) {
  const container = document.getElementById('calendarDays');
  if (!container) return;
  
  // Clear any existing days
  container.innerHTML = "";

  // We simplistic calendar covering the last 30 days or current month
  // We'll just build a grid from the 1st of the current month
  const now = new Date();
  let targetDate = new Date(now.getFullYear(), now.getMonth() + window.currentMonthOffset, 1);
  const year = targetDate.getFullYear();
  const month = targetDate.getMonth();
  
  document.getElementById('calendarMonthYear').textContent = targetDate.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });

  const firstDayOfMonth = new Date(year, month, 1);
  const startDayOfWeek = firstDayOfMonth.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Create empty slots for days before the 1st
  for (let i = 0; i < startDayOfWeek; i++) {
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'cal-day empty';
    container.appendChild(emptyDiv);
  }

  // Group history by date string 'YYYY-MM-DD'
  const historyByDate = {};
  history.forEach(item => {
    const d = new Date(item.created_at);
    // adjust for local timezone matching
    const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    if (!historyByDate[dateStr]) {
      historyByDate[dateStr] = [];
    }
    historyByDate[dateStr].push(item);
  });

  let currentStreak = 0;
  let streakCheck = new Date();

  // Draw actual days
  for (let day = 1; day <= daysInMonth; day++) {
    const dayDiv = document.createElement('div');
    dayDiv.className = 'cal-day';
    dayDiv.textContent = day;

    const dateStr = `${year}-${String(month + 1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const dateObj = new Date(year, month, day);
    
    // Highlight today
    if (dateObj.toDateString() === now.toDateString()) {
      dayDiv.classList.add('today-highlight');
    }

    if (historyByDate[dateStr]) {
      // Find avg or worst/best mood. Let's just take the first entry of the day
      const primaryEntry = historyByDate[dateStr][0];
      const mood = primaryEntry.selected_mood;
      
      if (['Awesome', 'Good'].includes(mood)) dayDiv.classList.add('mood-bg-good');
      else if (mood === 'Fine') dayDiv.classList.add('mood-bg-fine');
      else if (['Bad', 'Terrible'].includes(mood)) dayDiv.classList.add('mood-bg-bad');

      dayDiv.dataset.tooltip = `Mood: ${mood}\n${primaryEntry.journal_text.substring(0,20)}...`;
    }

    container.appendChild(dayDiv);

  }

  // Simple streak calc backward from today
  for (let i = 0; i < 365; i++) {
    const checkD = new Date(now.getTime() - i * 24*60*60*1000);
    const dStr = `${checkD.getFullYear()}-${String(checkD.getMonth() + 1).padStart(2,'0')}-${String(checkD.getDate()).padStart(2,'0')}`;
    if (historyByDate[dStr]) {
      currentStreak++;
    } else {
      break; 
    }
  }

  document.getElementById('streakLabel').textContent = `${currentStreak}-day`;

  // Draw Streak Week Grid (Last 7 Days ending today)
  const streakGrid = document.getElementById('streakWeekGrid');
  if (streakGrid) {
    streakGrid.innerHTML = ''; // clear
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    // Start from Sunday to Saturday of current week
    const currentDayOfWeek = now.getDay(); // 0 is Sunday
    const sundayDate = new Date(now.getTime() - currentDayOfWeek * 24*60*60*1000);
    
    for (let i = 0; i < 7; i++) {
      const dayDate = new Date(sundayDate.getTime() + i * 24*60*60*1000);
      const dStr = `${dayDate.getFullYear()}-${String(dayDate.getMonth() + 1).padStart(2,'0')}-${String(dayDate.getDate()).padStart(2,'0')}`;
      const isLogged = !!historyByDate[dStr];
      const isToday = (dayDate.toDateString() === now.toDateString());

      const itemDiv = document.createElement('div');
      itemDiv.className = 'streak-day-item';

      const iconDiv = document.createElement('div');
      iconDiv.className = `streak-day-icon ${isLogged ? 'checked' : 'empty'}`;
      iconDiv.textContent = isLogged ? '🔥' : '';

      const labelDiv = document.createElement('div');
      labelDiv.className = `streak-day-label ${isToday ? 'today' : ''}`;
      labelDiv.textContent = dayNames[dayDate.getDay()];

      itemDiv.appendChild(iconDiv);
      itemDiv.appendChild(labelDiv);
      streakGrid.appendChild(itemDiv);
    }
  }
}

function generateInsights(distribution, history) {
  const labels = Object.keys(distribution);
  const data = Object.values(distribution);
  const total = data.reduce((a, b) => a + b, 0);

  const freqSpan = document.getElementById('frequentEmotionText');
  const posSpan = document.getElementById('positivityRateText');
  const summaryList = document.getElementById('summaryInsightsList');

  if (total === 0) return;

  const maxVal = Math.max(...data);
  const maxLabel = labels[data.indexOf(maxVal)];
  freqSpan.textContent = maxLabel;

  const positiveTotal = (distribution['Awesome'] || 0) + (distribution['Good'] || 0);
  const neutralTotal = (distribution['Fine'] || 0);
  const negTotal = (distribution['Bad'] || 0) + (distribution['Terrible'] || 0);
  
  const positivity = Math.round((positiveTotal / total) * 100);
  posSpan.textContent = `${positivity}% Positive`;

  // Summary bullets
  summaryList.innerHTML = "";
  if (positivity > 50) {
    summaryList.innerHTML += `<li>Your mood has been generally uplifting recently.</li>`;
  }
  if (negTotal > positiveTotal) {
    summaryList.innerHTML += `<li>You've experienced more challenging days this period.</li>`;
  }
  
  // Smart Recommendation Logic
  if (negTotal > 0 || positivity < 50) {
    document.getElementById('reportsRecCard').style.display = "block";
    const recList = document.getElementById('reportsRecList');
    recList.innerHTML = `
      <li><strong>Breathing Exercise:</strong> Take 5 minutes to ground yourself.</li>
      <li><strong>Journaling:</strong> Let your negative thoughts flow honestly.</li>
      <li><strong>Walk:</strong> Gentle outdoor walks improve baseline stress levels.</li>
    `;
  }
}

