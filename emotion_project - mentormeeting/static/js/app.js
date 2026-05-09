const selectedMoodInput = document.getElementById("selectedMood");
const selectedSecondaryInput = document.getElementById("selectedSecondaryEmotion");
const selectedCauseInput = document.getElementById("selectedCause");
const journalText = document.getElementById("journalText");

const introScreen = document.getElementById("introScreen");
const startJournalingBtn = document.getElementById("startJournalingBtn");
const moodForm = document.getElementById("moodForm");

const toStep2Btn = document.getElementById("toStep2");
const toStep3Btn = document.getElementById("toStep3");
const toStep4Btn = document.getElementById("toStep4");

const backToStep1Btn = document.getElementById("backToStep1");
const backToStep2Btn = document.getElementById("backToStep2");
const backToStep3Btn = document.getElementById("backToStep3");

const moodGrid = document.getElementById("moodGrid");
const emotionGrid = document.getElementById("emotionGrid");
const causeGrid = document.getElementById("causeGrid");

const form = document.getElementById("moodForm");
const resultArea = document.getElementById("resultArea");
const resultBody = document.getElementById("resultBody");
const alertBox = document.getElementById("alertBox");

const analyzeBtn = document.getElementById("analyzeBtn");
const feedbackArea = document.getElementById("feedbackArea");
const feedbackQuestion = document.getElementById("feedbackQuestion");
const yesBtn = document.getElementById("yesBtn");
const noBtn = document.getElementById("noBtn");

// ---- Time-based greeting ----
function updateGreeting(username = "there") {
  const hour = new Date().getHours();
  let period = "morning";
  if (hour >= 12 && hour < 17) period = "afternoon";
  else if (hour >= 17) period = "evening";

  const title = document.getElementById("greetingTitle");
  if (title) {
    title.textContent = `Good ${period}, ${username}!`;
  }
}




const EMOTIONS_BY_MOOD = {
  Awesome: ["Happy", "Loved", "Joyful", "Relieved", "Grateful"],
  Good: ["Calm", "Okay", "Hopeful", "Content", "Supported"],
  Fine: ["Neutral", "Fine", "Slightly good", "Mild"],
  Bad: ["Sad", "Anxious", "Scared", "Disgusted"],
  Terrible: ["Angry", "Annoyed", "Sad", "Anxious", "Scared", "Disgusted"],
};

function clearAlert() {
  alertBox.style.display = "none";
  alertBox.textContent = "";
}

function setAlert(msg) {
  clearAlert();
  if (!msg) return;
  alertBox.textContent = msg;
  alertBox.style.display = "block";
}

function setStep(panelNumber) {
  const panels = document.querySelectorAll(".stepSection");
  panels.forEach((p) => {
    const n = p.getAttribute("data-panel");
    const isActive = n === String(panelNumber);
    p.style.display = "";
    p.classList.toggle("active-panel", isActive);
  });

  const steps = document.querySelectorAll(".step");
  steps.forEach((s) => {
    const n = s.getAttribute("data-step");
    s.classList.toggle("active", n === String(panelNumber));
  });

  // Save progress to localStorage
  localStorage.setItem("journalStep", panelNumber);
}

function clearMoodSelection() {
  selectedMoodInput.value = "";
  moodGrid.querySelectorAll(".mood-card").forEach((btn) => btn.classList.remove("selected"));
  toStep2Btn.disabled = true;
}

function clearEmotionSelection() {
  selectedSecondaryInput.value = "";
  emotionGrid.querySelectorAll(".emotion-chip").forEach((btn) => btn.classList.remove("selected"));
  toStep3Btn.disabled = true;
}

function clearCauseSelection() {
  selectedCauseInput.value = "";
  causeGrid.querySelectorAll(".cause-card").forEach((btn) => btn.classList.remove("selected"));
  toStep4Btn.disabled = true;
}

function renderEmotionGrid() {
  const mood = selectedMoodInput.value;
  emotionGrid.innerHTML = "";
  clearEmotionSelection();

  const list = EMOTIONS_BY_MOOD[mood] || [];
  list.forEach((label) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "emotion-chip";
    btn.textContent = label;
    btn.dataset.emotion = label;
    btn.addEventListener("click", () => {
      emotionGrid.querySelectorAll(".emotion-chip").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      selectedSecondaryInput.value = label;
      toStep3Btn.disabled = false;
      localStorage.setItem("journalEmotion", label);
    });
    emotionGrid.appendChild(btn);
  });
}

function getFormPayload() {
  return {
    selectedMood: selectedMoodInput.value,
    selectedSecondaryEmotion: selectedSecondaryInput.value,
    selectedCause: selectedCauseInput.value,
    journalText: journalText.value,
  };
}

function formatConfidencePercent(p) {
  if (p === null || p === undefined || Number.isNaN(p)) return "";
  return `${Math.round(p)}%`;
}

function renderResult(analysis, isMatch, selectedMood, recommendations = [], payload = null) {
  const predictedMood    = analysis.predicted_mood;
  const predictedEmotion = analysis.predicted_emotion;
  const secondaryEmotion = analysis.secondary_emotion;
  const confidence = analysis.confidence;
  const confPercent = formatConfidencePercent(confidence * 100);
  const isUnclear = predictedEmotion === "Mixed/Unclear";
  const allProbs = analysis.all_probabilities || {};

  let html = "";

  // ---- Crisis Banner ----
  if (analysis.show_alert) {
    html += `
      <div class="result-banner result-banner--crisis">
        <div class="banner-icon">⚠️</div>
        <div class="banner-content">
          <h4 class="banner-title">Safety Alert</h4>
          <p class="banner-text">We've detected crisis language. If you're feeling overwhelmed, please reach out to a trusted person or emergency services (like 988) immediately.</p>
          ${analysis.risk_level ? `<p class="banner-meta">Risk level: <strong>${analysis.risk_level}</strong></p>` : ""}
        </div>
      </div>
    `;
    resultBody.innerHTML = html;
    feedbackArea.style.display = "none";
    return;
  }

  // ---- Mixed/Unclear Banner ----
  if (isUnclear) {
    let bestEmotion = null;
    let bestProb = -1;
    for (const [emo, prob] of Object.entries(allProbs)) {
      if (prob > bestProb) { bestProb = prob; bestEmotion = emo; }
    }
    const bestPct = formatConfidencePercent(bestProb * 100);

    html += `
      <div class="result-banner result-banner--mismatch">
        <div class="banner-icon">☁️</div>
        <div class="banner-content">
          <h4 class="banner-title">Complex Feelings</h4>
          <p class="banner-text">Your journal suggests a mix of emotions that are hard to categorize simply.</p>
          ${bestEmotion ? `<p class="banner-meta">Strongest signal: <strong>${bestEmotion}</strong> (${bestPct} confidence)</p>` : ""}
        </div>
      </div>
    `;
    resultBody.innerHTML = html;
    feedbackArea.style.display = "none";
    return;
  }

  // ---- Equivalence Check ----
  const POSITIVE = new Set(["Awesome", "Good"]);
  const NEUTRAL = new Set(["Fine"]);
  const NEGATIVE = new Set(["Bad", "Terrible"]);
  const effectiveMatch = isMatch ||
    (POSITIVE.has(selectedMood) && POSITIVE.has(predictedMood)) ||
    (NEUTRAL.has(selectedMood) && NEUTRAL.has(predictedMood)) ||
    (NEGATIVE.has(selectedMood) && NEGATIVE.has(predictedMood));

  // ---- 1. Primary Analysis Card ----
  html += `
    <div class="analysis-hero-card">
      <div class="hero-main">
        <span class="hero-label">Detected Emotion</span>
        <h2 class="hero-value">${predictedEmotion}</h2>
        ${secondaryEmotion ? `<p class="hero-sub">with hints of <strong>${secondaryEmotion}</strong></p>` : ""}
      </div>
      
      <div class="hero-footer">
        ${effectiveMatch ?
      `<div class="match-badge match-badge--yes">✨ Aligned with your choice</div>` :
      `<div class="match-badge match-badge--no">🔍 Different from your selection</div>`
    }
      </div>
    </div>
  `;

  // ---- 2. AI Confidence Section ----
  const smConfPercent = formatConfidencePercent(confidence * 100);
  const nbConfPercent = formatConfidencePercent(analysis.nb_confidence * 100);

  html += `
    <div class="confidence-section">
      <h3 class="section-title-premium">AI Confidence</h3>
      <div class="conf-grid-compact">
        <div class="conf-item-new">
          <div class="conf-top">
            <span class="conf-type">Primary Engine</span>
            <span class="conf-pct">${smConfPercent}</span>
          </div>
          <div class="conf-bar-new"><div class="conf-fill-new" style="width: ${smConfPercent}"></div></div>
        </div>
        <div class="conf-item-new">
          <div class="conf-top">
            <span class="conf-type">Validation Engine</span>
            <span class="conf-pct">${nbConfPercent}</span>
          </div>
          <div class="conf-bar-new"><div class="conf-fill-new experimental" style="width: ${nbConfPercent}"></div></div>
        </div>
      </div>
    </div>
  `;

  // ---- 3. Mental Health Insight (The "What are these?" part) ----
  if (analysis.depression_level && analysis.anxiety_level) {
    html += `
      <div class="insight-section-premium">
        <h3 class="section-title-premium">Mental Health Overview</h3>
        <div class="insight-bento-grid">
          
          <!-- Wellness Card -->
          <div class="bento-card bento-wellness">
            <div class="wellness-gauge-wrapper">
              <svg viewBox="0 0 36 36" class="gauge-svg">
                <path class="gauge-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                <path class="gauge-fill" stroke-dasharray="${analysis.wellness_score}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                <text x="18" y="20.35" class="gauge-text">${analysis.wellness_score}</text>
              </svg>
            </div>
            <div class="wellness-meta">
              <span class="meta-label">Wellness Score</span>
              <span class="meta-status status-${analysis.wellness_level.toLowerCase().replace(" ", "-")}">${analysis.wellness_level}</span>
            </div>
          </div>
          
          <!-- Levels Card -->
          <div class="bento-card bento-levels">
            <div class="level-row">
              <span class="level-name">Depression</span>
              <span class="level-tag tag-${analysis.depression_level.toLowerCase()}">${analysis.depression_level}</span>
            </div>
            <div class="level-row">
              <span class="level-name">Anxiety</span>
              <span class="level-tag tag-${analysis.anxiety_level.toLowerCase()}">${analysis.anxiety_level}</span>
            </div>
          </div>
          
          <!-- Tips Card -->
          <div class="bento-card bento-tips">
            <h4 class="tips-header">Personalized Guidance</h4>
            <ul class="tips-list-new">
              ${(analysis.recommendations || []).map(r => `
                <li><span class="tip-bullet"></span> ${r}</li>
              `).join("")}
            </ul>
          </div>

        </div>
      </div>
    `;
  }

  resultBody.innerHTML = html;

  // Render Smart Recommendations
  const recsContainer = document.getElementById("recommendationsArea");
  if (analysis.show_alert || isUnclear) {
    if (recsContainer) recsContainer.style.display = "none";
  } else if (recommendations && recommendations.length > 0 && recsContainer) {
    recsContainer.style.display = "block";
    const recsGrid = document.getElementById("recommendationsGrid");
    recsGrid.innerHTML = "";
    
    // Fetch all activities to match images
    fetch('/api/activities_data')
      .then(res => res.json())
      .then(data => {
        const allActs = Object.values(data.categories || {}).flat();
        
        recommendations.forEach(rec => {
            const matchedAct = allActs.find(a => a.title.toLowerCase() === rec.title.toLowerCase());
            const imageUrl = matchedAct ? matchedAct.image_url : null;
            const imageHtml = imageUrl ? 
              `<img src="${imageUrl}" alt="${rec.title}" class="card-image" style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px;">` : 
              rec.icon || '✨';

            recsGrid.innerHTML += `
              <div class="activity-card">
                <div class="card-image-box" style="height: 120px; display: flex; align-items: center; justify-content: center; font-size: 3rem; background: var(--sage-light); border-radius: 12px; margin-bottom: 12px; overflow: hidden;">
                  ${imageHtml}
                </div>
                <div class="card-content">
                  <h3 class="card-title">${rec.title}</h3>
                  <p class="card-desc" style="font-size: 0.85rem; color: var(--text-muted);">${rec.category || 'Wellness'}</p>
                </div>
                <div class="card-footer">
                  <span class="duration">${rec.duration || '5 min'}</span>
                  <a href="/activities?open=${encodeURIComponent(rec.title)}" class="btn btn-primary btn-pill btn-sm">Start</a>
                </div>
              </div>
            `;
        });
      });
  } else if (recsContainer) {
    recsContainer.style.display = "none";
  }

  // Add "New Entry" and "Edit Text" buttons
  const resultFooterHtml = `
    <div class="result-footer-actions" style="margin-top: 32px; border-top: 1px solid var(--border-light); padding-top: 24px; display: flex; gap: 16px; justify-content: center;">
      <button type="button" class="btn btn-outline btn-pill" id="editJournalBtn">Edit Entry</button>
      <button type="button" class="btn btn-primary btn-pill" id="startNewEntryBtn">Start New Entry</button>
    </div>
  `;
  resultBody.insertAdjacentHTML('beforeend', resultFooterHtml);

  // Listener for New Entry
  document.getElementById("startNewEntryBtn").addEventListener("click", () => {
    ["journalAnalysisResult", "journalStep", "journalMood", "journalEmotion", "journalCause", "journalText"].forEach(k => localStorage.removeItem(k));
    window.location.reload();
  });

  // Listener for Edit Entry (Start from Step 1)
  document.getElementById("editJournalBtn").addEventListener("click", () => {
    const analysisData = JSON.parse(localStorage.getItem("journalAnalysisResult") || "{}");
    // Restore data to localStorage so resumeProgress can pick it up
    if (analysisData.payload) {
      localStorage.setItem("journalMood", analysisData.payload.selectedMood || "");
      localStorage.setItem("journalSecondaryEmotion", analysisData.payload.selectedSecondaryEmotion || "");
      localStorage.setItem("journalEmotion", analysisData.payload.selectedSecondaryEmotion || ""); // Duplicate for consistency
      localStorage.setItem("journalCause", analysisData.payload.selectedCause || "");
      localStorage.setItem("journalText", analysisData.payload.journalText || "");
    }
    // Start from step 1 so they can re-verify everything
    localStorage.setItem("journalStep", "1");
    localStorage.removeItem("journalAnalysisResult");
    window.location.reload(); 
  });
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    const msg = data && data.error ? data.error : "Request failed";
    throw new Error(msg);
  }
  return data;
}

/* Samsung Health–style: calm intro, then card-based steps */
// ---- Progress Persistence & Restoration ----
function saveProgress() {
  localStorage.setItem("journalMood", selectedMoodInput.value);
  localStorage.setItem("journalEmotion", selectedSecondaryInput.value);
  localStorage.setItem("journalCause", selectedCauseInput.value);
  localStorage.setItem("journalText", journalText.value);
  localStorage.setItem("journalLastDate", new Date().toDateString());
}

function resumeProgress() {
  const savedStep = localStorage.getItem("journalStep");
  if (!savedStep) return;

  // Show form, hide intro
  introScreen.hidden = true;
  moodForm.hidden = false;

  // Restore step
  setStep(savedStep);

  // 1. Restore Mood
  const savedMood = localStorage.getItem("journalMood");
  if (savedMood) {
    const moodBtn = moodGrid.querySelector(`.mood-card[data-mood="${savedMood}"]`);
    if (moodBtn) moodBtn.click();
  }

  // 2. Restore Emotion
  const savedEmo = localStorage.getItem("journalEmotion");
  if (savedEmo && savedMood) {
    renderEmotionGrid();
    setTimeout(() => {
      const emoChip = emotionGrid.querySelector(`.emotion-chip[data-emotion="${savedEmo}"]`);
      if (emoChip) emoChip.click();
    }, 150);
  }

  // 3. Restore Cause
  const savedCause = localStorage.getItem("journalCause");
  if (savedCause) {
    const causeBtn = causeGrid.querySelector(`.cause-card[data-cause="${savedCause}"]`);
    if (causeBtn) causeBtn.click();
  }

  // 4. Restore Text
  const savedText = localStorage.getItem("journalText");
  if (savedText) {
    journalText.value = savedText;
    if (savedText.trim().length > 0) analyzeBtn.disabled = false;
  }
}

window.initDashboard = function () {
  const savedStep = localStorage.getItem("journalStep");
  const savedResult = localStorage.getItem("journalAnalysisResult");
  const lastSavedDate = localStorage.getItem("journalLastDate");
  const today = new Date().toDateString();

  // If the saved data is from a different day, clear it
  if (lastSavedDate && lastSavedDate !== today) {
    localStorage.removeItem("journalStep");
    localStorage.removeItem("journalAnalysisResult");
    localStorage.removeItem("journalMood");
    localStorage.removeItem("journalEmotion");
    localStorage.removeItem("journalCause");
    localStorage.removeItem("journalText");
    localStorage.removeItem("journalLastDate");
    console.log("Cleared old journal draft from previous day");
    startJournalingBtn.textContent = "Start Journaling";
    return;
  }

  if (savedResult) {
    // If we have a saved result, show it automatically
    const analysisData = JSON.parse(savedResult);
    introScreen.hidden = true;
    moodForm.hidden = false; 
    
    // Restore the writing area content and step
    if (analysisData.payload && analysisData.payload.journalText) {
      journalText.value = analysisData.payload.journalText;
    }
    setStep(4); 
    
    resultArea.style.display = "block";
    renderResult(analysisData.analysis, analysisData.isMatch, analysisData.selectedMood, analysisData.recommendations, analysisData.payload);
  } else if (savedStep) {
    // If we have a draft, show the intro but with "Resume" text
    introScreen.hidden = false;
    moodForm.hidden = true;
    startJournalingBtn.textContent = "Resume Journaling";

    // Also pre-fill the form in the background so it's ready when they click Resume
    resumeProgress();
    // But then hide it again because resumeProgress() unhides it
    introScreen.hidden = false;
    moodForm.hidden = true;
  } else {
    startJournalingBtn.textContent = "Start Journaling";
  }

  console.log("Dashboard initialized");
};

startJournalingBtn.addEventListener("click", () => {
  introScreen.hidden = true;
  moodForm.hidden = false;

  if (localStorage.getItem("journalStep")) {
    resumeProgress();
  } else {
    setStep(1);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// Stepper click interactions
document.querySelectorAll(".step").forEach((step) => {
  step.addEventListener("click", () => {
    const stepNum = parseInt(step.getAttribute("data-step"));
    if (stepNum === 2 && selectedMoodInput.value) renderEmotionGrid();
    setStep(stepNum);
  });
});

// Persist journal text
journalText.addEventListener("input", () => {
  localStorage.setItem("journalText", journalText.value);
});

moodGrid.querySelectorAll(".mood-card").forEach((btn) => {
  btn.addEventListener("click", () => {
    moodGrid.querySelectorAll(".mood-card").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    const mood = btn.dataset.mood || "";
    selectedMoodInput.value = mood;
    toStep2Btn.disabled = !mood;
    localStorage.setItem("journalMood", mood);
  });
});

causeGrid.querySelectorAll(".cause-card").forEach((btn) => {
  btn.addEventListener("click", () => {
    causeGrid.querySelectorAll(".cause-card").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    const cause = btn.dataset.cause || "";
    selectedCauseInput.value = cause;
    toStep4Btn.disabled = !cause;
    localStorage.setItem("journalCause", cause);
  });
});

toStep2Btn.addEventListener("click", () => {
  if (!selectedMoodInput.value) return;
  renderEmotionGrid();
  setStep(2);
});

toStep3Btn.addEventListener("click", () => {
  if (!selectedSecondaryInput.value) return;
  setStep(3);
});

toStep4Btn.addEventListener("click", () => {
  if (!selectedCauseInput.value) return;
  setStep(4);
});

backToStep1Btn.addEventListener("click", () => {
  setStep(1);
});

backToStep2Btn.addEventListener("click", () => {
  setStep(2);
});

backToStep3Btn.addEventListener("click", () => {
  setStep(3);
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAlert();
  feedbackArea.style.display = "none";
  resultArea.style.display = "block";
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing…";

  try {
    const payload = getFormPayload();

    const resp = await postJson("/api/analyze", payload);
    const analysis = resp.analysis;
    const isMatch = resp.isMatch;
    const selectedMood = payload.selectedMood;
    const recommendations = resp.recommendations || [];

    // Store journalId for feedback
    window.lastJournalId = resp.meta ? resp.meta.journalId : null;

    renderResult(analysis, isMatch, selectedMood, recommendations, payload);

    // Persist result and payload so it stays if they navigate away and come back
    localStorage.setItem("journalAnalysisResult", JSON.stringify({
      analysis,
      isMatch,
      selectedMood,
      recommendations,
      payload // Store original payload for editing later
    }));

    // We no longer clear the draft here immediately, 
    // we clear it when the user clicks "Start New Entry".

    if (analysis.show_alert) {
      feedbackArea.style.display = "none";
    } else {
      // Always show feedback area to allow saving/confirming, 
      // or at least make sure it's available if needed.
      feedbackArea.style.display = "block";
      // Reset feedback buttons
      feedbackArea.innerHTML = `
        <p class="feedback-prompt">Was this prediction accurate?</p>
        <div class="feedback-btns">
            <button type="button" class="btn btn-primary btn-pill btn-sm" id="yesFeedbackBtn">Yes</button>
            <button type="button" class="btn btn-outline btn-pill btn-sm" id="noFeedbackBtn">No</button>
        </div>
      `;
      // Re-attach listeners because we just overwrote the HTML
      attachFeedbackListeners();
    }

    resultArea.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    setAlert(err.message);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
  }
});

function attachFeedbackListeners() {
  const yes = document.getElementById("yesFeedbackBtn");
  const no = document.getElementById("noFeedbackBtn");
  if (!yes || !no) return;

  yes.addEventListener("click", async () => {
    yes.disabled = true;
    no.disabled = true;
    yes.textContent = "Saving…";
    try {
      await postJson("/api/feedback", { journalId: window.lastJournalId, feedback: "Yes" });
      feedbackArea.innerHTML = `<div class="resultLine ok">Saved. Thank you — your feedback helps improve the AI.</div>`;
    } catch (err) {
      yes.disabled = false;
      no.disabled = false;
      yes.textContent = "Yes";
      setAlert("Failed to save: " + err.message);
    }
  });

  no.addEventListener("click", async () => {
    yes.disabled = true;
    no.disabled = true;
    no.textContent = "Saving…";
    try {
      await postJson("/api/feedback", { journalId: window.lastJournalId, feedback: "No" });
      feedbackArea.innerHTML = `<div class="resultLine ok">Noted — we'll use your feedback to improve.</div>`;
    } catch (err) {
      yes.disabled = false;
      no.disabled = false;
      no.textContent = "No";
      setAlert("Failed to save: " + err.message);
    }
  });
}


// Logout: Clear all local storage
document.querySelectorAll('a[href="/logout"]').forEach(a => {
  a.addEventListener('click', () => {
    localStorage.clear();
  });
});

