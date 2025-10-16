document.addEventListener("DOMContentLoaded", async () => {
  const video = document.getElementById("camera");
  if (!video) return;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" } // ← 外カメラを優先
    });
    video.srcObject = stream;
  } catch (err) {
    console.error("カメラ起動エラー:", err);
  }
});
