/**
 * Bootstrap script that loads D3 and the graph wrapper.
 * This is injected as a <script type="module"> tag before the React app mounts.
 */
import * as d3 from 'https://cdn.jsdelivr.net/npm/d3@7/+esm'
window.d3 = d3

// Load the wrapper (which loads graph.js and config.js)
import './graph-wrapper.js'
