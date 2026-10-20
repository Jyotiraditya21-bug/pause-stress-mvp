/**
 * Client-side ONNX Runtime Web session manager for the Pause experimental face model.
 * Loads the 3.84 MB MobileNetV3-Small ONNX model locally from public/models/pause_stress_model.onnx.
 * Preserves zero-server-upload privacy guarantee (runs 100% locally on device).
 */
import * as ort from 'onnxruntime-web/wasm';
import wasmModuleUrl from 'onnxruntime-web/ort-wasm-simd-threaded.mjs?url';
import wasmBinaryUrl from 'onnxruntime-web/ort-wasm-simd-threaded.wasm?url';
import { softmax, TemporalEMAFilter, MODEL_INPUT_SIZE } from './mlInference.js';

let sessionPromise = null;
let activeSession = null;
let sessionGeneration = 0;
let scanGeneration = 0;
const emaFilter = new TemporalEMAFilter(0.20);

/**
 * Configure ONNX Runtime Web environment.
 */
function configureEnvironment() {
  if (ort.env && ort.env.wasm) {
    ort.env.wasm.numThreads = 1;
    ort.env.wasm.simd = true;
    // Resolve assets from the installed package, including Vite's base path.
    // The generic ORT entry point requests JSEP assets that are not shipped here.
    ort.env.wasm.wasmPaths = {
      mjs: new URL(wasmModuleUrl, window.location.href).href,
      wasm: new URL(wasmBinaryUrl, window.location.href).href
    };
  }
}

/**
 * Lazily loads and caches the ONNX inference session.
 * @returns {Promise<ort.InferenceSession>}
 */
export async function getModelSession() {
  if (activeSession) return activeSession;
  if (sessionPromise) return sessionPromise;

  const generation = sessionGeneration;
  configureEnvironment();

  sessionPromise = (async () => {
    try {
      const base = import.meta.env.BASE_URL || '/';
      const modelPath = base.endsWith('/') ? `${base}models/pause_stress_model.onnx` : `${base}/models/pause_stress_model.onnx`;
      const session = await ort.InferenceSession.create(modelPath, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all'
      });
      if (generation !== sessionGeneration) {
        await session.release();
        throw new Error('Model initialization was cancelled.');
      }
      activeSession = session;
      return session;
    } catch (err) {
      if (generation === sessionGeneration) sessionPromise = null;
      throw new Error(`Failed to initialize on-device ML model: ${err?.message || err}`);
    }
  })();

  return sessionPromise;
}

/**
 * Runs a single forward pass over a normalized Float32Array tensor.
 * @param {Float32Array} nchwData - Normalized pixel tensor [1, 3, 224, 224]
 * @returns {Promise<{ rawStressProb: number, smoothedStressProb: number, logits: number[] }>}
 */
export async function predictFaceStress(nchwData) {
  const generation = scanGeneration;
  if (!(nchwData instanceof Float32Array) || nchwData.length !== 3 * MODEL_INPUT_SIZE ** 2 || !nchwData.every(Number.isFinite)) {
    throw new Error('Invalid model input; no prediction is available.');
  }
  const session = await getModelSession();
  const inputTensor = new ort.Tensor('float32', nchwData, [1, 3, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE]);
  let results;
  try {
    results = await session.run({ input: inputTensor });
    if (generation !== scanGeneration) throw new Error('Scan prediction was cancelled.');
    const outputTensor = results.output || Object.values(results)[0];
    const logits = Array.from(outputTensor.data);
    const probs = softmax(logits);
    return { rawStressProb: probs.stress, smoothedStressProb: emaFilter.update(probs.stress), logits };
  } finally {
    inputTensor.dispose();
    for (const tensor of Object.values(results || {})) tensor.dispose();
  }
}

/**
 * Resets the temporal smoothing filter (call at the beginning of a scan).
 */
export function resetMLScan() {
  scanGeneration++;
  emaFilter.reset();
}

/**
 * Releases the ONNX session from browser memory.
 */
export async function disposeModelSession() {
  sessionGeneration++;
  scanGeneration++;
  sessionPromise = null;
  if (activeSession) {
    try {
      await activeSession.release();
    } catch {}
    activeSession = null;
    sessionPromise = null;
  }
  emaFilter.reset();
}
