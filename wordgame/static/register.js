// Live checklist under the signup fields. The server re-checks everything.
(() => {
  const form = document.querySelector("[data-register]");
  if (!form) return;

  const checks = {
    username: {
      letters: (v) => /^[A-Za-z]+$/.test(v),
      length5: (v) => v.length >= 5,
      mixed: (v) => /[a-z]/.test(v) && /[A-Z]/.test(v),
    },
    password: {
      length5: (v) => v.length >= 5,
      alpha: (v) => /[A-Za-z]/.test(v),
      digit: (v) => /\d/.test(v),
      special: (v) => /[$%*@]/.test(v),
    },
  };

  for (const [field, rules] of Object.entries(checks)) {
    const input = form.elements[field];
    const list = form.querySelector(`[data-rules-for="${field}"]`);
    const update = () => {
      for (const [name, test] of Object.entries(rules)) {
        list.querySelector(`[data-rule="${name}"]`).classList.toggle("met", test(input.value));
      }
    };
    input.addEventListener("input", update);
    update();
  }
})();
