const repository = 'https://github.com/Jyotiraditya21-bug/pause-stress-mvp/tree/main/stress_math';

export default function Experiment() {
  return <>
    <p className="eyebrow">OPTIONAL LOCAL EXPERIMENT</p>
    <h1>A mathematical facial index.</h1>
    <p className="intro">Explore a training-free facial behavior index with live camera or offline video on your computer. This experimental index has not been validated as a measurement of personal stress.</p>
    <section className="panel">
      <h2>Run the experiment locally</h2>
      <p>GitHub Pages hosts this browser demo. The separate Python experiment requires Python 3.11 or 3.12 and runs locally; this page does not execute it.</p>
      <p><a className="primary" href={`${import.meta.env.BASE_URL}experiment/stress_math.zip`} download>Download experiment code</a></p>
      <p><a href={repository} target="_blank" rel="noreferrer">View code and full run instructions on GitHub ↗</a></p>
      <p><a href={`${import.meta.env.BASE_URL}experiment/README.md`}>Read the experiment guide</a></p>
      <pre style={{overflowX:'auto',fontSize:'.85rem',lineHeight:1.7}}><code>{`# Unzip the download, then open its folder in Terminal\npython3.12 -m venv stress_math/.venv\nstress_math/.venv/bin/python -m pip install -r stress_math/requirements.txt\nstress_math/.venv/bin/python -m stress_math.evaluate --live`}</code></pre>
      <p>Live mode asks for recording consent and saves a four-minute session locally: two minutes relaxed, then two minutes timed arithmetic. No video is uploaded.</p>
    </section>
    <div className="cards">
      <article><h2>Fixed rules</h2><p>A 25-second personal baseline, 75 selected landmarks, fixed equal weights, and a sigma floor. No training or tuning on test data.</p></article>
      <article><h2>Compare the evidence</h2><p>Compare each feature alone, the index without pulse features, and all available features. Evaluate AUC, paired differences and subject-bootstrap intervals, plus 1,000 label permutations.</p></article>
      <article><h2>Check signal coverage</h2><p>Exclude videos with less than 40% usable frames after pose and speaking/smiling checks. Reports show coverage, exclusions and processing time.</p></article>
    </div>
    <section className="panel"><h2>Current verification</h2><p>Nine synthetic tests passed. Real webcam sessions and public-dataset performance remain unverified. The existing browser check-in has no video stress scorer, so it is not used as a predictive baseline.</p><p>The experimental 0–100 index is not a percentage of stress. A value of 50 corresponds to baseline feature means; its threshold is not clinically validated.</p></section>
  </>;
}
