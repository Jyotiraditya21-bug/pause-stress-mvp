import React from 'react';

export default function Experiment(){
  return <section className="info-page">
    <p>The Calm index uses MediaPipe landmarks and a fixed mathematical comparison. The default mode compares brow and mouth geometry with a generic reference. Personal mode compares the same scan with a baseline captured when you chose to calibrate while calm.</p>
    <section className="pz-panel"><h2>What it can say</h2><p>It describes whether the captured facial geometry was above or below this experimental reference during one scan.</p></section>
    <section className="pz-panel"><h2>What it cannot say</h2><p>It is not a medical or psychological measurement, cannot tell how stressed you feel, and has no established accuracy on a real labeled dataset.</p></section>
    <section className="pz-panel"><h2>What affects it</h2><p>Lighting, camera angle, facial expression, movement and natural facial shape can all change the number. The range on Results describes variation within that scan, not clinical certainty.</p></section>
  </section>;
}
