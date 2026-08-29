(() => {
  "use strict";

  const app = document.querySelector(".fortune-app");
  const rotor = document.querySelector(".wheel-rotor");
  const spinButton = document.querySelector(".spin-button");
  const availability = document.querySelector(".availability");
  const countdown = document.querySelector(".countdown");
  const lastPrize = document.querySelector(".last-prize");
  const lastPrizeValue = lastPrize.querySelector("strong");
  const errorMessage = document.querySelector(".error-message");
  const registrationPanel = document.querySelector(".registration-panel");
  const registrationLink = document.querySelector(".registration-link");
  const telegram = window.Telegram?.WebApp;
  const prizeOrder = [5, 10, 15, 25, 60, 100];
  let nextSpinAt = null;
  let countdownTimer = null;
  let rotation = 0;

  telegram?.ready();
  telegram?.expand();

  function hapticImpact() {
    telegram?.HapticFeedback?.impactOccurred("medium");
  }

  function hapticSuccess() {
    telegram?.HapticFeedback?.notificationOccurred("success");
  }

  function requestOptions() {
    return {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Telegram-Init-Data": telegram?.initData || "",
      },
      body: "{}",
    };
  }

  async function request(url) {
    const response = await fetch(url, requestOptions());
    const data = await response.json();
    if (!response.ok) {
      const failure = new Error(data.error || "Не удалось выполнить вращение. Попробуйте ещё раз.");
      failure.status = response.status;
      failure.data = data;
      throw failure;
    }
    return data;
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = false;
  }

  function clearError() {
    errorMessage.hidden = true;
    errorMessage.textContent = "";
  }

  function formatRemaining(milliseconds) {
    const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${days} дн ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function updateCountdown() {
    if (!nextSpinAt) {
      return;
    }
    const remaining = nextSpinAt.getTime() - Date.now();
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      countdownTimer = null;
      countdown.hidden = true;
      availability.textContent = "Вращение доступно сейчас";
      availability.classList.add("is-ready");
      spinButton.disabled = false;
      return;
    }
    countdown.textContent = `Следующее вращение через ${formatRemaining(remaining)}`;
    countdown.hidden = false;
  }

  function showCooldown(prize, nextAt) {
    lastPrizeValue.textContent = prize;
    lastPrize.hidden = false;
    availability.textContent = "Следующая попытка ещё не доступна";
    availability.classList.remove("is-ready");
    spinButton.disabled = true;
    nextSpinAt = new Date(nextAt);
    clearInterval(countdownTimer);
    updateCountdown();
    countdownTimer = setInterval(updateCountdown, 1000);
  }

  function showReady() {
    nextSpinAt = null;
    countdown.hidden = true;
    availability.textContent = "Вращение доступно сейчас";
    availability.classList.add("is-ready");
    spinButton.disabled = false;
  }

  function showRegistration(url) {
    document.querySelector(".wheel-stage").hidden = true;
    document.querySelector(".result-panel").hidden = true;
    spinButton.hidden = true;
    registrationLink.href = url;
    registrationPanel.hidden = false;
  }

  function animateToPrize(prize, nextAt) {
    const prizeIndex = prizeOrder.indexOf(prize);
    rotation += 2160 - prizeIndex * 60 - (rotation % 360);
    rotor.style.setProperty("--rotation", `${rotation}deg`);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.setTimeout(() => {
      hapticSuccess();
      showCooldown(prize, nextAt);
      spinButton.textContent = "Крутить колесо";
    }, reducedMotion ? 0 : 5200);
  }

  async function loadStatus() {
    if (!telegram?.initData) {
      availability.textContent = "Откройте колесо через Telegram";
      showError("Telegram не передал данные для входа.");
      return;
    }
    try {
      const state = await request(app.dataset.statusUrl);
      if (!state.registered) {
        showRegistration(state.registration_url);
      } else if (state.can_spin) {
        showReady();
      } else {
        showCooldown(state.last_prize, state.next_spin_at);
      }
    } catch (error) {
      availability.textContent = "Не удалось проверить доступность";
      showError(error.message);
    }
  }

  spinButton.addEventListener("click", async () => {
    clearError();
    spinButton.disabled = true;
    spinButton.textContent = "Определяем приз…";
    hapticImpact();
    try {
      const result = await request(app.dataset.spinUrl);
      animateToPrize(result.prize_apples, result.next_spin_at);
    } catch (error) {
      spinButton.textContent = "Крутить колесо";
      if (error.status === 409) {
        showCooldown(error.data.last_prize, error.data.next_spin_at);
        return;
      }
      spinButton.disabled = false;
      showError(error.message);
    }
  });

  loadStatus();
})();
