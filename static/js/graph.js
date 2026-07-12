const TOP_N = 40;

let currentUrl = null;

function trimGraph(graph, n = TOP_N) {
  // Drop edges that reference a trimmed-out node, or D3's forceLink
  // will throw trying to resolve a missing source/target id.
  const topNodes = [...graph.nodes]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, n);
  const survivingNames = new Set(topNodes.map(node => node.file));
  const edges = graph.edges.filter(
    edge => survivingNames.has(edge.file1) && survivingNames.has(edge.file2)
  );
  return { nodes: topNodes, edges };
}

function toD3Format(graph) {
  const nodes = graph.nodes.map(node => ({
    id: node.file,
    weight: node.weight,
  }));
  const links = graph.edges.map(edge => ({
    source: edge.file1,
    target: edge.file2,
    value: edge.weight,
  }));
  return { nodes, links };
}

function renderGraph(graph) {
  d3.select('#graph').selectAll('*').remove();

  const width = document.getElementById('graph').clientWidth;
  const height = 800;
  const svg = d3
    .select('#graph')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const [minWeight, maxWeight] = d3.extent(graph.nodes, d => d.weight);
  // scaleSqrt, not scaleLinear: circle area grows with r squared, so a linear
  // scale would make weight differences look bigger than they are.
  const radiusScale = d3
    .scaleSqrt()
    .domain([minWeight, maxWeight])
    .range([8, 36]);
  graph.nodes.forEach(d => (d.r = radiusScale(d.weight)));

  const simulation = d3
    .forceSimulation(graph.nodes)
    // distance/strength/collide radius tuned by hand to stop labels
    // overlapping on dense clusters — not D3 defaults.
    .force(
      'link',
      d3
        .forceLink(graph.links)
        .id(d => d.id)
        .distance(90)
    )
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'collide',
      d3.forceCollide().radius(d => d.r + 25)
    );

  const g = svg.append('g');

  const link = g
    .selectAll('line')
    .data(graph.links)
    .join('line')
    .attr('stroke', '#999');

  const node = g
    .selectAll('circle')
    .data(graph.nodes)
    .join('circle')
    .attr('r', d => d.r)
    .attr('fill', '#69b3a2');

  const drag = d3
    .drag()
    // Reheat the simulation so other nodes react while dragging.
    .on('start', (event, d) => {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      // fx/fy pin the node to a fixed position, overriding the simulation.
      d.fx = d.x;
      d.fy = d.y;
    })
    .on('drag', (event, d) => {
      d.fx = event.x;
      d.fy = event.y;
    })
    .on('end', (event, d) => {
      // Let the simulation cool back down.
      if (!event.active) simulation.alphaTarget(0);
      // Release the pin so forces can move the node again.
      d.fx = null;
      d.fy = null;
    });

  node.call(drag);

  node.on('click', (_event, d) => showCommits(d.id, currentUrl));

  const label = g
    .selectAll('text')
    .data(graph.nodes)
    .join('text')
    .text(d => {
      const name = d.id.split('/').pop();
      return name.length > 20 ? name.slice(0, 20) + '…' : name;
    })
    .attr('font-size', 10)
    .attr('dx', 8)
    .attr('dy', 4);

  svg.call(
    d3.zoom().on('zoom', event => {
      g.attr('transform', event.transform);
    })
  );

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    node
      // Clamp position to canvas bounds and write it back to d.x/d.y so the
      // simulation keeps building on the clamped value, not the raw one.
      .attr('cx', d => (d.x = Math.max(d.r, Math.min(width - d.r, d.x))))
      .attr('cy', d => (d.y = Math.max(d.r, Math.min(height - d.r, d.y))));
    label.attr('x', d => d.x).attr('y', d => d.y);
  });
}

function showError(message, containerId = 'graph') {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  const p = document.createElement('p');
  p.className = 'error';
  p.style.color = 'red';
  p.textContent = message;
  container.appendChild(p);
}

function renderPanel(filename, commits) {
  const panel = document.getElementById('panel');
  panel.innerHTML = '';

  const heading = document.createElement('h3');
  heading.textContent = filename;
  panel.appendChild(heading);

  const list = document.createElement('ul');
  commits.forEach(commit => {
    const item = document.createElement('li');
    const shortSha = commit.sha.slice(0, 7);
    const summary = commit.message.split('\n')[0];
    item.textContent = `${shortSha} — ${summary} (${commit.author}, ${commit.committed_at})`;
    list.appendChild(item);
  });
  panel.appendChild(list);

  const summaryEl = document.createElement('p');
  summaryEl.id = 'summary';
  summaryEl.className = 'summary-loading';
  summaryEl.textContent = 'Generating summary…';
  panel.appendChild(summaryEl);
}

function showSummary(filename, url) {
  if (!url) return;

  fetch('/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, filename }),
  })
    .then(response =>
      response.json().then(data => {
        if (!response.ok) {
          throw new Error(data.error || `Request failed: ${response.status}`);
        }
        return data;
      })
    )
    .then(data => {
      const summaryEl = document.getElementById('summary');
      if (summaryEl) {
        summaryEl.textContent = data.summary;
        summaryEl.className = '';
      }
    })
    .catch(() => {
      const summaryEl = document.getElementById('summary');
      if (summaryEl) {
        summaryEl.textContent = 'summary unavailable';
        summaryEl.className = '';
      }
    });
}

function showCommits(filename, url) {
  if (!url) return;

  fetch('/commits', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, filename }),
  })
    .then(response =>
      response.json().then(data => {
        if (!response.ok) {
          throw new Error(data.error || `Request failed: ${response.status}`);
        }
        return data;
      })
    )
    .then(commits => {
      renderPanel(filename, commits);
      // Summary is a separate, slower request (Gemini call, not cached on
      // first view) — commits render immediately, summary fills in afterwards.
      showSummary(filename, url);
    })
    .catch(error => showError(error.message, 'panel'));
}

document.getElementById('repo-form').addEventListener('submit', event => {
  event.preventDefault();

  const url = document.getElementById('repo-url').value;
  currentUrl = url;
  const submitBtn = document.getElementById('submit-btn');

  submitBtn.disabled = true;
  submitBtn.textContent = 'Loading…';

  fetch('/graph', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
    .then(response =>
      response.json().then(data => {
        if (!response.ok) {
          throw new Error(data.error || `Request failed: ${response.status}`);
        }
        return data;
      })
    )
    .then(data => renderGraph(toD3Format(trimGraph(data))))
    .catch(error => showError(error.message))
    .finally(() => {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Visualize';
    });
});

// Writes cursor position as CSS custom properties (--mouse-x/--mouse-y)
// that the stylesheet's radial-gradient background reads to follow the cursor.
const graphContainer = document.getElementById('graph');
graphContainer.addEventListener('mousemove', event => {
  const rect = graphContainer.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  graphContainer.style.setProperty('--mouse-x', `${x}px`);
  graphContainer.style.setProperty('--mouse-y', `${y}px`);
});
