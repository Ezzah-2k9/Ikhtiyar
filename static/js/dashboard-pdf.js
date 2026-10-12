(() => {
  'use strict';

  const dataElement = document.getElementById('dashboard-data');
  const downloadButton = document.getElementById('download-report');
  const statusElement = document.getElementById('pdf-status');

  if (!dataElement || !downloadButton) return;

  const PALETTE = {
    forest: [23, 58, 52],       // #173a34
    forestLight: [39, 82, 70],  // #275246
    brass: [212, 187, 140],     // #d4bb8c
    ink: [40, 53, 48],
    muted: [111, 126, 117],
    line: [225, 232, 227],
    paper: [247, 249, 247],
    white: [255, 255, 255],
    green: [65, 126, 98]
  };

  const PAGE_MARGIN = 16;
  const FOOTER_RESERVE = 23;
  const TABLE_COLUMNS = [
    { key: 'date', label: 'DATE', width: 27, align: 'left' },
    { key: 'route', label: 'ROUTE', width: 64, align: 'left' },
    { key: 'mode', label: 'MODE', width: 25, align: 'left' },
    { key: 'distance', label: 'DISTANCE', width: 20, align: 'right' },
    { key: 'cost', label: 'COST', width: 22, align: 'right' },
    { key: 'saved', label: 'CO2 SAVED', width: 20, align: 'right' }
  ];

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function fixed(value, places = 2) {
    return number(value).toFixed(places);
  }

  function safeText(value, fallback = '—') {
    const text = String(value ?? '').replace(/\s+/g, ' ').trim();
    return text || fallback;
  }

  function dateLabel(value) {
    const raw = safeText(value, '—');
    if (/^\d{4}-\d{2}-\d{2}/.test(raw)) {
      const [year, month, day] = raw.slice(0, 10).split('-');
      return `${day}/${month}/${year}`;
    }
    return raw;
  }

  function setFont(doc, style = 'normal') {
    doc.setFont('helvetica', style);
  }

  async function loadBrandLogo() {
    const image = document.querySelector('.navbar .logo img, .brand-picture img, .site-footer .footer-logo img');
    if (!image) return null;

    if (!image.complete) {
      await Promise.race([
        new Promise((resolve) => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', resolve, { once: true });
        }),
        new Promise((resolve) => window.setTimeout(resolve, 1500))
      ]);
    }
    if (!image.naturalWidth || !image.naturalHeight) return null;

    try {
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d');
      if (!context) return null;
      context.drawImage(image, 0, 0);
      return { dataUrl: canvas.toDataURL('image/png'), width: canvas.width, height: canvas.height };
    } catch (error) {
      console.warn('Could not read the Ikhtiyar logo for the PDF report:', error);
      return null;
    }
  }

  function drawLogoBadge(doc, logo, x, y, width, height) {
    // Warm gold tile keeps the black transparent logo legible on the forest header.
    doc.setFillColor(...PALETTE.brass);
    doc.roundedRect(x, y, width, height, 1.5, 1.5, 'F');

    if (logo && logo.dataUrl && logo.width > 0 && logo.height > 0) {
      const inset = 3;
      const scale = Math.min((width - inset * 2) / logo.width, (height - inset * 2) / logo.height);
      const imageWidth = logo.width * scale;
      const imageHeight = logo.height * scale;
      doc.addImage(
        logo.dataUrl, 'PNG',
        x + (width - imageWidth) / 2,
        y + (height - imageHeight) / 2,
        imageWidth, imageHeight,
        'ikhtiyar-brand-logo', 'FAST'
      );
      return;
    }

    // Still give the report a branded gold lockup if no image asset is available.
    doc.setTextColor(...PALETTE.forest);
    doc.setFontSize(height < 18 ? 6.5 : 8);
    setFont(doc, 'bold');
    doc.text('IKHTIYAR', x + width / 2, y + height / 2 + 1, { align: 'center' });
  }

  function drawCover(doc, data, pageWidth, logo) {
    // A calm, compact masthead with a clear hierarchy and no heavy decoration.
    doc.setFillColor(...PALETTE.forest);
    doc.rect(0, 0, pageWidth, 46, 'F');
    drawLogoBadge(doc, logo, PAGE_MARGIN, 9, 43, 27);

    doc.setTextColor(220, 231, 224);
    doc.setFontSize(7.2);
    setFont(doc, 'bold');
    doc.text('THOUGHTFUL MOBILITY', PAGE_MARGIN + 49, 20);
    doc.setFontSize(6.4);
    setFont(doc, 'normal');
    doc.text('UNITED ARAB EMIRATES', PAGE_MARGIN + 49, 27);

    doc.setTextColor(...PALETTE.brass);
    doc.setFontSize(7);
    setFont(doc, 'bold');
    doc.text('PERSONAL ACTIVITY REPORT', pageWidth - PAGE_MARGIN, 17, { align: 'right' });

    doc.setTextColor(...PALETTE.white);
    doc.setFontSize(8.5);
    setFont(doc, 'normal');
    doc.text(`Prepared for ${safeText(data.username, 'Ikhtiyar member')}`, pageWidth - PAGE_MARGIN, 24, { align: 'right' });

    doc.setTextColor(220, 231, 224);
    doc.setFontSize(7.5);
    doc.text(new Intl.DateTimeFormat('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric'
    }).format(new Date()), pageWidth - PAGE_MARGIN, 31, { align: 'right' });

    doc.setTextColor(...PALETTE.ink);
    doc.setFontSize(19);
    setFont(doc, 'normal');
    doc.text('Your journeys, in perspective.', PAGE_MARGIN, 63);

    doc.setTextColor(...PALETTE.muted);
    doc.setFontSize(8.5);
    doc.text('A concise overview of your travel activity and environmental impact.', PAGE_MARGIN, 70);
  }

  function drawMetricCards(doc, stats, pageWidth, startY) {
    const contentWidth = pageWidth - PAGE_MARGIN * 2;
    const gap = 3;
    const cardWidth = (contentWidth - gap * 3) / 4;
    const cardHeight = 29;
    const items = [
      { label: 'TOTAL TRIPS', value: String(Math.round(number(stats.total_trips))) },
      { label: 'CO2 SAVED', value: `${fixed(stats.co2_saved)} kg` },
      { label: 'TOTAL COST', value: `${fixed(stats.total_cost)} AED` },
      { label: 'GREEN POINTS', value: String(Math.round(number(stats.green_points))) }
    ];

    items.forEach((item, index) => {
      const x = PAGE_MARGIN + index * (cardWidth + gap);
      doc.setFillColor(...PALETTE.paper);
      doc.roundedRect(x, startY, cardWidth, cardHeight, 1.5, 1.5, 'F');
      doc.setDrawColor(...PALETTE.line);
      doc.setLineWidth(0.25);
      doc.roundedRect(x, startY, cardWidth, cardHeight, 1.5, 1.5, 'S');
      doc.setFillColor(...PALETTE.brass);
      doc.rect(x, startY, cardWidth, 0.8, 'F');

      doc.setTextColor(...PALETTE.muted);
      doc.setFontSize(6.2);
      setFont(doc, 'bold');
      doc.text(item.label, x + 3, startY + 10);

      doc.setTextColor(...PALETTE.forest);
      doc.setFontSize(item.value.length > 12 ? 9.2 : 11.5);
      setFont(doc, 'bold');
      doc.text(item.value, x + 3, startY + 21);
    });

    return startY + cardHeight;
  }

  function tableHeader(doc, y, pageWidth) {
    const contentWidth = pageWidth - PAGE_MARGIN * 2;
    doc.setFillColor(...PALETTE.forest);
    doc.roundedRect(PAGE_MARGIN, y, contentWidth, 9, 1.2, 1.2, 'F');

    let x = PAGE_MARGIN;
    doc.setTextColor(...PALETTE.white);
    doc.setFontSize(6.4);
    setFont(doc, 'bold');
    TABLE_COLUMNS.forEach((column) => {
      const textX = column.align === 'right' ? x + column.width - 2 : x + 2;
      doc.text(column.label, textX, y + 5.8, { align: column.align });
      x += column.width;
    });
    return y + 9;
  }

  function tripCellValues(trip) {
    const mode = safeText(trip.chosen_transport, 'Unknown');
    return {
      date: dateLabel(trip.trip_date),
      route: `${safeText(trip.origin_name, 'Unknown')} to ${safeText(trip.destination_name, 'Unknown')}`,
      mode: mode.charAt(0).toUpperCase() + mode.slice(1),
      distance: `${fixed(trip.distance_km, 1)} km`,
      cost: `${fixed(trip.chosen_cost)} AED`,
      saved: `${fixed(Math.max(0, number(trip.co2_saved)))} kg`
    };
  }

  function drawTripRow(doc, trip, y, index, pageWidth) {
    const contentWidth = pageWidth - PAGE_MARGIN * 2;
    const rowPadding = 2;
    const textSize = 7.1;
    const lineHeight = 3.7;
    const cells = tripCellValues(trip);
    let maxLines = 1;

    const prepared = TABLE_COLUMNS.map((column) => {
      const width = column.width - rowPadding * 2;
      const lines = doc.splitTextToSize(cells[column.key], width).slice(0, 2);
      maxLines = Math.max(maxLines, lines.length);
      return { column, lines };
    });

    const rowHeight = Math.max(10, maxLines * lineHeight + 4.5);
    if (index % 2 === 1) {
      doc.setFillColor(...PALETTE.paper);
      doc.rect(PAGE_MARGIN, y, contentWidth, rowHeight, 'F');
    }

    doc.setDrawColor(...PALETTE.line);
    doc.setLineWidth(0.2);
    doc.line(PAGE_MARGIN, y + rowHeight, pageWidth - PAGE_MARGIN, y + rowHeight);

    let x = PAGE_MARGIN;
    prepared.forEach(({ column, lines }) => {
      const textX = column.align === 'right' ? x + column.width - rowPadding : x + rowPadding;
      doc.setTextColor(...(column.key === 'saved' && number(trip.co2_saved) > 0 ? PALETTE.green : PALETTE.ink));
      doc.setFontSize(textSize);
      setFont(doc, column.key === 'saved' && number(trip.co2_saved) > 0 ? 'bold' : 'normal');
      const textY = y + 4.8;
      doc.text(lines, textX, textY, { align: column.align, lineHeightFactor: 1.15 });
      x += column.width;
    });

    return y + rowHeight;
  }

  function drawContinuationHeader(doc, pageWidth, logo) {
    doc.setFillColor(...PALETTE.forest);
    doc.rect(0, 0, pageWidth, 20, 'F');
    drawLogoBadge(doc, logo, PAGE_MARGIN, 3, 30, 14);
    doc.setTextColor(...PALETTE.brass);
    doc.setFontSize(7);
    doc.text('ACTIVITY REPORT · CONTINUED', pageWidth - PAGE_MARGIN, 12, { align: 'right' });
  }

  function drawFooter(doc, pageWidth, pageHeight, pageNumber, pageCount) {
    const ruleY = pageHeight - 18;
    doc.setDrawColor(...PALETTE.line);
    doc.setLineWidth(0.3);
    doc.line(PAGE_MARGIN, ruleY, pageWidth - PAGE_MARGIN, ruleY);

    doc.setTextColor(...PALETTE.muted);
    doc.setFontSize(6.8);
    setFont(doc, 'normal');
    doc.text('IKHTIYAR  ·  THOUGHTFUL MOBILITY', PAGE_MARGIN, pageHeight - 11);
    doc.setTextColor(...PALETTE.forest);
    setFont(doc, 'bold');
    doc.text(`${pageNumber} / ${pageCount}`, pageWidth - PAGE_MARGIN, pageHeight - 11, { align: 'right' });
  }

  function buildReport(data, JsPDF, logo) {
    const doc = new JsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4', compress: true });
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const trips = Array.isArray(data.recent) ? data.recent : [];

    drawCover(doc, data, pageWidth, logo);
    doc.setTextColor(...PALETTE.forest);
    doc.setFontSize(7);
    setFont(doc, 'bold');
    doc.text('AT A GLANCE', PAGE_MARGIN, 84);

    let y = drawMetricCards(doc, data.stats || {}, pageWidth, 89) + 11;
    doc.setTextColor(...PALETTE.forest);
    doc.setFontSize(12);
    setFont(doc, 'normal');
    doc.text('Recent journeys', PAGE_MARGIN, y + 3);
    doc.setTextColor(...PALETTE.muted);
    doc.setFontSize(7);
    doc.text(`${trips.length} ${trips.length === 1 ? 'journey' : 'journeys'} shown`, pageWidth - PAGE_MARGIN, y + 3, { align: 'right' });
    y += 8;
    y = tableHeader(doc, y, pageWidth);

    if (!trips.length) {
      doc.setFillColor(...PALETTE.paper);
      doc.rect(PAGE_MARGIN, y, pageWidth - PAGE_MARGIN * 2, 18, 'F');
      doc.setTextColor(...PALETTE.muted);
      doc.setFontSize(8);
      setFont(doc, 'normal');
      doc.text('No trips have been recorded yet.', PAGE_MARGIN + 4, y + 10);
    } else {
      trips.forEach((trip, index) => {
        // Measure the row before drawing so it never collides with the page footer.
        const values = tripCellValues(trip);
        const maxLines = Math.max(...TABLE_COLUMNS.map((column) =>
          doc.splitTextToSize(values[column.key], column.width - 4).slice(0, 2).length
        ));
        const estimatedHeight = Math.max(10, maxLines * 3.7 + 4.5);
        if (y + estimatedHeight > pageHeight - FOOTER_RESERVE) {
          doc.addPage();
          drawContinuationHeader(doc, pageWidth, logo);
          y = tableHeader(doc, 27, pageWidth);
        }
        y = drawTripRow(doc, trip, y, index, pageWidth);
      });
    }

    const pageCount = doc.getNumberOfPages();
    for (let page = 1; page <= pageCount; page += 1) {
      doc.setPage(page);
      drawFooter(doc, pageWidth, pageHeight, page, pageCount);
    }

    return doc;
  }

  function reportFilename(username) {
    const safeName = safeText(username, 'member')
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'member';
    const date = new Date().toISOString().slice(0, 10);
    return `ikhtiyar-activity-report-${safeName}-${date}.pdf`;
  }

  downloadButton.addEventListener('click', async () => {
    const originalContent = downloadButton.innerHTML;
    downloadButton.disabled = true;
    downloadButton.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Preparing report…';
    if (statusElement) statusElement.textContent = 'Preparing your activity report.';

    try {
      const data = JSON.parse(dataElement.textContent || '{}');
      const JsPDF = window.jspdf && window.jspdf.jsPDF;
      if (!JsPDF) throw new Error('The PDF library did not load. Please refresh and try again.');
      const logo = await loadBrandLogo();
      const doc = buildReport(data, JsPDF, logo);
      doc.save(reportFilename(data.username));
      if (statusElement) statusElement.textContent = 'Your activity report is ready.';
    } catch (error) {
      console.error('PDF generation error:', error);
      if (statusElement) statusElement.textContent = error.message || 'Could not generate the report.';
    } finally {
      downloadButton.innerHTML = originalContent;
      downloadButton.disabled = false;
    }
  });
})();
