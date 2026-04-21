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

// ---- Time-based greeting (title only, badge stays static) ----
(function setGreeting() {
  const hour = new Date().getHours();
  let period = "morning";
  if (hour >= 12 && hour < 17) period = "afternoon";
  else if (hour >= 17) period = "evening";

  const title = document.getElementById("greetingTitle");
  if (title) {
    // Extract the name part rendered by Flask (everything after the comma)
    const current = title.textContent.trim();
    const namePart = current.includes(",") ? current.split(",").slice(1).join(",").trim() : "there!";
    title.textContent = `Good ${period}, ${namePart}`;
  }
})();


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
    // Remove the inline display style if it's there
    p.style.display = ""; 
    p.classList.toggle("active-panel", isActive);
  });

  const steps = document.querySelectorAll(".step");
  steps.forEach((s) => {
    const n = s.getAttribute("data-step");
    s.classList.toggle("active", n === String(panelNumber));
  });
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

function renderResult(analysis, isMatch, selectedMood, recommendations = []) {
  const predictedMood    = analysis.predicted_mood;
  const predictedEmotion = analysis.predicted_emotion;
  const secondaryEmotion = analysis.secondary_emotion;
  const confidence       = analysis.confidence;
  const confPercent      = formatConfidencePercent(confidence * 100);
  const isUnclear        = predictedEmotion === "Mixed/Unclear";
  const allProbs         = analysis.all_probabilities || {};

  let html = "";

  // ---- Crisis ----
  if (analysis.show_alert) {
    html += `<div class="resultLine warn"><strong>Crisis language detected.</strong></div>`;
    if (analysis.risk_level)
      html += `<div class="resultLine warn">Risk level: <strong>${analysis.risk_level}</strong></div>`;
    if (analysis.matched_phrases && analysis.matched_phrases.length)
      html += `<div class="resultLine warn">Flagged phrases: ${analysis.matched_phrases.join(", ")}</div>`;
    html += `<div class="resultLine warn">If this feels urgent, please reach out to a trusted person or emergency services right now.</div>`;
    resultBody.innerHTML = html;
    feedbackArea.style.display = "none";
    return;
  }

  // ---- Mixed / low confidence — show best-guess emotion anyway ----
  if (isUnclear) {
    // Find the highest probability emotion from all_probabilities
    let bestEmotion = null;
    let bestProb = -1;
    for (const [emo, prob] of Object.entries(allProbs)) {
      if (prob > bestProb) { bestProb = prob; bestEmotion = emo; }
    }
    const bestPct = formatConfidencePercent(bestProb * 100);

    html += `<div class="resultLine">Your feelings seem <strong>mixed or hard to pin down</strong> right now — and that's completely valid.</div>`;
    if (bestEmotion) {
      html += `<div class="resultLine">Strongest detected emotion: <strong>${bestEmotion}</strong> <span style="opacity:.7">(${bestPct} confidence)</span></div>`;
    }
    html += `<div class="resultLine" style="opacity:.8">The AI couldn't commit to a single clear emotion — write a bit more for a sharper result.</div>`;
    resultBody.innerHTML = html;
    feedbackArea.style.display = "none";
    return;
  }

  // ---- Mood groupings for equivalence ----
  const POSITIVE = new Set(["Awesome", "Good"]);
  const NEUTRAL = new Set(["Fine"]);
  const NEGATIVE = new Set(["Bad", "Terrible"]);
  const effectiveMatch = isMatch ||
    (POSITIVE.has(selectedMood) && POSITIVE.has(predictedMood)) ||
    (NEUTRAL.has(selectedMood) && NEUTRAL.has(predictedMood)) ||
    (NEGATIVE.has(selectedMood) && NEGATIVE.has(predictedMood));

  // ---- Primary emotion always shown first ----
  html += `<div class="resultLine">Main emotion detected: <strong>${predictedEmotion}</strong></div>`;
  if (secondaryEmotion)
    html += `<div class="resultLine">Also present: <strong>${secondaryEmotion}</strong></div>`;

  // ---- Mood match / mismatch ----
  const LOW_CONFIDENCE = confidence < 0.55;
  if (effectiveMatch) {
    html += `<div class="resultLine ok">Your feelings and your words align.</div>`;
  } else if (LOW_CONFIDENCE) {
    html += `<div class="resultLine warn">The model is not very confident in this read. You picked <strong>${selectedMood}</strong>; its tentative guess from wording is <strong>${predictedMood}</strong>. Trust what you actually feel.</div>`;
  } else {
    html += `<div class="resultLine warn">Mood comparison: you selected <strong>${selectedMood}</strong>, while the journal text leans toward <strong>${predictedMood}</strong>.</div>`;
  }

  if (LOW_CONFIDENCE && !effectiveMatch) {
    html += `<div class="resultLine" style="opacity:.85">Tip: a longer entry usually gives clearer signals than a single sentence.</div>`;
  }

  const smConfPercent   = formatConfidencePercent(confidence * 100);
  const nbConfPercent   = formatConfidencePercent(analysis.nb_confidence * 100);

  html += `
    <div class="resultLine">AI Analysis Comparison:</div>
    <div class="confidence-comparison">
      <div class="conf-item">
        <span class="conf-label">Softmax Regression (Current Main)</span>
        <div class="conf-bar-bg"><div class="conf-bar" style="width: ${smConfPercent}"></div></div>
        <div class="conf-val"><strong>${smConfPercent}</strong> confident in <strong>${predictedEmotion}</strong></div>
      </div>
      <div class="conf-item">
        <span class="conf-label">Naive Bayes (New Experimental)</span>
        <div class="conf-bar-bg"><div class="conf-bar nb" style="width: ${nbConfPercent}"></div></div>
        <div class="conf-val"><strong>${nbConfPercent}</strong> confident in <strong>${analysis.nb_emotion}</strong></div>
      </div>
    </div>
  `;


  resultBody.innerHTML = html;

  // Render Smart Recommendations if any are returned

  const recsContainer = document.getElementById("recommendationsArea");
  if (analysis.show_alert || isUnclear) {
      if (recsContainer) recsContainer.style.display = "none";
  } else if (recommendations && recommendations.length > 0 && recsContainer) {
      recsContainer.style.display = "block";
      const recsGrid = document.getElementById("recommendationsGrid");
      recsGrid.innerHTML = "";
      recommendations.forEach(rec => {
          recsGrid.innerHTML += `
            <div class="rec-card">
              <div class="rec-icon img-slot">&nbsp;</div>
              <div class="rec-info">
                <h3>${rec.title}</h3>
                <p>${rec.duration} • <span class="rec-category">${rec.category}</span></p>
              </div>
              <a href="/activities" class="btn btn-outline btn-pill rec-btn">Start</a>
            </div>
          `;
      });
  } else if (recsContainer) {
      recsContainer.style.display = "none";
  }

  if (!effectiveMatch) {
    feedbackArea.style.display = "block";
    feedbackQuestion.textContent = "Does this reading feel accurate to you?";
  } else {
    feedbackArea.style.display = "none";
  }
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
startJournalingBtn.addEventListener("click", () => {
  introScreen.hidden = true;
  moodForm.hidden = false;
  // ---- Pre-filling logic for "one entry per day" ----
  function handlePreFill() {
    const entry = window.todayEntry;
    if (!entry) return;

    console.log("Pre-filling today's entry:", entry);

    // 1. Fill Mood
    const moodBtn = moodGrid.querySelector(`.mood-card[data-mood="${entry.selected_mood}"]`);
    if (moodBtn) {
      moodBtn.click();
    }

    // 2. Fill Secondary Emotion
    if (entry.selected_secondary_emotion) {
      // We need to wait a bit for Step 2 chips to be generated
      setTimeout(() => {
        const emoChip = emotionGrid.querySelector(`.emotion-chip[data-emotion="${entry.selected_secondary_emotion}"]`);
        if (emoChip) emoChip.click();
      }, 100);
    }

    // 3. Fill Cause
    if (entry.selected_cause) {
      const causeBtn = causeGrid.querySelector(`.cause-card[data-cause="${entry.selected_cause}"]`);
      if (causeBtn) causeBtn.click();
    }

    // 4. Fill Journal Text
    if (entry.journal_text) {
      journalText.value = entry.journal_text;
      if (journalText.value.trim().length > 0) {
        analyzeBtn.disabled = false;
      }
    }
  }

  // Initial set
  setStep(1);
  handlePreFill();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

moodGrid.querySelectorAll(".mood-card").forEach((btn) => {
  btn.addEventListener("click", () => {
    moodGrid.querySelectorAll(".mood-card").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    selectedMoodInput.value = btn.dataset.mood || "";
    toStep2Btn.disabled = !selectedMoodInput.value;
  });
});

causeGrid.querySelectorAll(".cause-card").forEach((btn) => {
  btn.addEventListener("click", () => {
    causeGrid.querySelectorAll(".cause-card").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    selectedCauseInput.value = btn.dataset.cause || "";
    toStep4Btn.disabled = !selectedCauseInput.value;
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

    renderResult(analysis, isMatch, selectedMood, recommendations);

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


// End of app.js

