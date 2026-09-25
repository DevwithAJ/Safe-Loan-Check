(() => {
  const splash = document.getElementById("appSplash");
  const seen = sessionStorage.getItem("slcSplashSeen");
  if (splash) {
    const delay = seen ? 80 : 650;
    setTimeout(() => {
      splash.classList.add("hide");
      sessionStorage.setItem("slcSplashSeen", "1");
    }, delay);
  }

  const menuToggle = document.getElementById("menuToggle");
  const nav = document.getElementById("mainNav");
  if (menuToggle && nav) {
    menuToggle.addEventListener("click", () => nav.classList.toggle("open"));
    nav.querySelectorAll("a").forEach(a => a.addEventListener("click", () => nav.classList.remove("open")));
  }

  const revealItems = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    revealItems.forEach(el => io.observe(el));
  } else {
    revealItems.forEach(el => el.classList.add("visible"));
  }

  const back = document.getElementById("backToTop");
  if (back) {
    window.addEventListener("scroll", () => back.classList.toggle("show", window.scrollY > 500));
    back.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  // Cost inputs are truly opt-in: disabled and empty while the toggle is OFF.
  document.querySelectorAll("[data-cost-toggle]").forEach(toggle => {
    const form = toggle.closest("form");
    const fieldset = form ? form.querySelector("[data-cost-fields]") : null;
    if (!fieldset) return;

    const sync = (clearWhenOff = false) => {
      fieldset.disabled = !toggle.checked;
      fieldset.classList.toggle("cost-fields-disabled", !toggle.checked);
      if (!toggle.checked && clearWhenOff) {
        fieldset.querySelectorAll("input").forEach(input => { input.value = ""; });
      }
    };

    sync(false);
    toggle.addEventListener("change", () => sync(true));
  });

  const overlay = document.getElementById("processingOverlay");
  document.querySelectorAll("[data-processing-form]").forEach(form => {
    form.addEventListener("submit", () => {
      if (overlay) {
        overlay.classList.add("show");
        overlay.setAttribute("aria-hidden", "false");
      }
    });
  });
})();
