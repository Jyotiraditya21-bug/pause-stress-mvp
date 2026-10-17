/**
 * Client-side ONNX Runtime Web session manager for the Pause experimental face model.
 * Loads the 3.84 MB MobileNetV3-Small ONNX model locally from public/models/pause_stress_model.onnx.
 * Preserves zero-server-upload privacy guarantee (runs 100% locally on device).
 */
import * as ort from 'onnxruntime-web';
import { softmax, TemporalEMAFilter, MODEL_INPUT_SIZE } from './mlInference.js';

let sessionPromise = null;
let activeSession = null;
const emaFilter = new TemporalEMAFilter(0.20);

/**
 * Configure ONNX Runtime Web environment.
 */
function configureEnvironment() {
  if (ort.env && ort.env.wasm) {
    ort.env.wasm.numThreads = 1;
    ort.env.wasm.simd = true;
    const base = import.meta.env.BASE_URL || '/';
    ort.env.wasm.wasmPaths = base.endsWith('/') ? `${base}onnx/` : `${base}/onnx/`;
  }
}

/**
 * Lazily loads and caches the ONNX inference session.
 * @returns {Promise<ort.InferenceSession>}
 */
export async function getModelSession() {
  if (activeSession) return activeSession;
  if (sessionPromise) return sessionPromise;

  configureEnvironment();

  sessionPromise = (async () => {
    try {
      const base = import.meta.env.BASE_URL || '/';
      const modelPath = base.endsWith('/') ? `${base}models/pause_stress_model.onnx` : `${base}/models/pause_stress_model.onnx`;
      const session = await ort.InferenceSession.create(modelPath, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all'
      });
      activeSession = session;
      return session;
    } catch (err) {
      sessionPromise = null;
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
  const session = await getModelSession();
  const inputTensor = new ort.Tensor('float32', nchwData, [1, 3, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE]);

  const feeds = { input: inputTensor };
  const results = await session.run(feeds);

  // Output name from model_spec is 'output'
  const outputTensor = results.output || Object.values(results)[0];
  const logits = Array.from(outputTensor.data);

  const probs = softmax(logits);
  const smoothed = emaFilter.update(probs.stress);

  return {
    rawStressProb: probs.stress,
    smoothedStressProb: smoothed,
    logits
  };
}

/**
 * Resets the temporal smoothing filter (call at the beginning of a scan).
 */
export function resetMLScan() {
  emaFilter.reset();
}

/**
 * Releases the ONNX session from browser memory.
 */
export async function disposeModelSession() {
  if (activeSession) {
    try {
      await activeSession.release();
    } catch {}
    activeSession = null;
    sessionPromise = null;
  }
  emaFilter.reset();
}
