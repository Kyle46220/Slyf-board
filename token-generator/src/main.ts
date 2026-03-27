import * as OTPAuth from "otpauth";

const secret = import.meta.env.VITE_TOTP_SECRET as string;
if (!secret) {
  throw new Error("VITE_TOTP_SECRET is not set");
}

const totp = new OTPAuth.TOTP({
  secret: OTPAuth.Secret.fromBase32(secret),
  period: 300,
  digits: 6,
  algorithm: "SHA1",
});

function renderCode() {
  const code = totp.generate();
  const codeEl = document.getElementById("code")!;
  codeEl.textContent = code;
}

function secondsUntilExpiry(): number {
  return totp.period - (Math.floor(Date.now() / 1000) % totp.period);
}

function renderTimer() {
  const timerEl = document.getElementById("timer")!;
  timerEl.textContent = `Expires in ${secondsUntilExpiry()}s`;
}

document.getElementById("copy-btn")!.addEventListener("click", () => {
  const code = document.getElementById("code")!.textContent!;
  navigator.clipboard.writeText(code);
  const btn = document.getElementById("copy-btn")!;
  btn.textContent = "Copied!";
  setTimeout(() => { btn.textContent = "Copy"; }, 1500);
});

function tick() {
  renderCode();
  renderTimer();
}

renderCode();
renderTimer();
setInterval(tick, 1000);
