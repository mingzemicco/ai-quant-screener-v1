const fs = require('fs');
const path = require('path');
const MarkdownGenerator = require('./markdown-generator');

// Configuration
const BLOG_DIR = path.join(__dirname, '../content/blog');

// Ensure directory exists
if (!fs.existsSync(BLOG_DIR)) {
  fs.mkdirSync(BLOG_DIR, { recursive: true });
}

const generator = new MarkdownGenerator();

// 1. Global Macro Article
const macroArticle = generator.generateArticle(
  "Global Markets: The Divergence Between Fed and ECB Policy",
  "The global economic landscape in 2026 is defined by a striking divergence in monetary policy.",
  `
The global economic landscape in 2026 is defined by a striking divergence in monetary policy. While the Federal Reserve signals a "higher for longer" stance to combat stubborn services inflation, the European Central Bank (ECB) faces a rapidly cooling eurozone economy, prompting calls for earlier rate cuts.

## The Federal Reserve's Stance

Despite signs of softening in the labor market, U.S. GDP growth remains resilient. The latest FOMC minutes reveal a committee that is still wary of declaring victory over inflation.

## The ECB's Dilemma

In contrast, the Eurozone is flirting with technical recession. Manufacturing data from Germany continues to disappoint, and credit demand has slumped to decade lows.

## Implications for EUR/USD

This policy divergence creates a classic setup for **EUR/USD weakness**. As the interest rate differential widens in favor of the Dollar, capital flows are likely to seek the higher yield and safety of US Treasuries.
  `,
  ["Macro", "FX", "EURUSD"],
  "Global Macro"
);

// 2. Technical Analysis Article
const techArticle = generator.generateArticle(
  "USD/JPY Technical Outlook: Is 150 the New Floor?",
  "Technical analysis of the Japanese Yen against the US Dollar.",
  `
The Japanese Yen continues to trade at historically weak levels against the US Dollar, with the **USD/JPY** pair consolidating firmly above the psychological 150.00 handle.

## Technical Analysis: The 150.00 Support

Technically, the pair has formed a robust base at 149.80 - 150.20. Repeated tests of this zone have been met with aggressive buying, suggesting strong institutional demand.

## Key Levels to Watch

| Level | Type | Significance |
|---|---|---|
| 152.00 | Resistance | Recent swing high & potential breakout trigger |
| 150.00 | Support | Psychological floor and option barrier |
| 148.50 | Support | 50-day Exponential Moving Average |
  `,
  ["FX", "Technical Analysis", "USDJPY"],
  "Technical Analysis"
);

// Write files
fs.writeFileSync(path.join(BLOG_DIR, macroArticle.filename), macroArticle.content);
console.log(`✅ Created: ${macroArticle.filename}`);

fs.writeFileSync(path.join(BLOG_DIR, techArticle.filename), techArticle.content);
console.log(`✅ Created: ${techArticle.filename}`);
