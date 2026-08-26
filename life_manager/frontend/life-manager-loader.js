(async () => {
  const MANIFEST_URL = "/local/life-manager-manifest.json";

  try {
    const response = await fetch(`${MANIFEST_URL}?_=${Date.now()}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`Manifest HTTP ${response.status}`);
    }

    const manifest = await response.json();
    const version = String(manifest.version || "").trim();
    const file = String(manifest.file || "").trim();

    if (!version || !file) {
      throw new Error("Ungültiges Life-Manager-Manifest");
    }

    console.info(`Life Manager loader: loading frontend ${version}`);

    await import(`${file}?v=${encodeURIComponent(version)}`);
  } catch (error) {
    console.error("Life Manager frontend loader failed:", error);
  }
})();
