// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { remarkMermaid } from './plugins/remark-mermaid.mjs';

// Published to GitHub Pages under /emulators/, so every generated link needs
// that base. Docs content is generated from /docs by scripts/sync-docs.mjs
// before build. /docs stays the single source of truth, and its files keep
// working as plain Markdown on GitHub.
export default defineConfig({
  site: 'https://calvinchengx.github.io',
  base: '/emulators/',
  markdown: { remarkPlugins: [remarkMermaid] },
  integrations: [
    starlight({
      title: 'Emulators',
      description:
        'The emulator ecosystem: local emulators of Entra ID, ARM, Key Vault, APIM, Fabric, Databricks and Snowflake, plus a reference data product proven on three engines. Built to accelerate AI-driven development.',
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/calvinchengx/emulators',
        },
      ],
      components: { Head: './src/components/Head.astro' },
      sidebar: [
        {
          label: 'Start here',
          items: [{ slug: 'index' }, { slug: '00-overview' }, { slug: '01-the-map' }],
        },
        {
          label: 'The ecosystem',
          items: [
            { slug: '02-the-emulators' },
            { slug: '03-the-data-product-matrix' },
          ],
        },
        {
          label: 'The argument',
          items: [
            { slug: '04-building-with-ai-agents' },
            { slug: '05-why-these-emulators' },
          ],
        },
        {
          label: 'Using it',
          items: [
            { slug: '06-getting-started' },
            { slug: '08-ci-status' },
            { slug: '07-roadmap' },
          ],
        },
        {
          label: 'Repos',
          items: [
            { label: 'azure-emulators (the BOM)', link: 'https://calvinchengx.github.io/azure-emulators/', attrs: { target: '_blank' } },
            { label: 'entra-emulator', link: 'https://calvinchengx.github.io/entra-emulator/', attrs: { target: '_blank' } },
            { label: 'arm-emulator', link: 'https://calvinchengx.github.io/arm-emulator/', attrs: { target: '_blank' } },
            { label: 'azure-keyvault-emulator', link: 'https://calvinchengx.github.io/azure-keyvault-emulator/', attrs: { target: '_blank' } },
            { label: 'azure-apim-emulator', link: 'https://calvinchengx.github.io/azure-apim-emulator/', attrs: { target: '_blank' } },
            { label: 'fabric-emulator', link: 'https://calvinchengx.github.io/fabric-emulator/', attrs: { target: '_blank' } },
            { label: 'databricks-emulator', link: 'https://calvinchengx.github.io/databricks-emulator/', attrs: { target: '_blank' } },
            { label: 'snowflake-emulator', link: 'https://github.com/calvinchengx/snowflake-emulator', attrs: { target: '_blank' } },
          ],
        },
      ],
    }),
  ],
});
