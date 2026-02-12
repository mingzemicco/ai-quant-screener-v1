const fs = require('fs');
const path = require('path');

class MarkdownGenerator {
  generateArticle(title, summary, content, tags = [], category = 'General') {
    const date = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    
    // Frontmatter for Hugo/Jekyll/Next.js
    const fileContent = `---
title: "${title}"
date: ${date}
description: "${summary}"
tags: [${tags.map(t => `"${t}"`).join(', ')}]
category: "${category}"
author: "Qian LIU"
---

${content}
`;

    return {
      filename: `${date}-${slug}.md`,
      content: fileContent
    };
  }
}

module.exports = MarkdownGenerator;
