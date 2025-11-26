const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

/**
 * @param {object} config
 * @param {string} config.filename - HTML file to process and override
 * @param {boolean} config.env - Whether to replace env vars or not (default - `false`)
 * @param {string} config.envPrefix - Limit env vars to pick (default - `REACT_APP_`)
 */
const HtmlPlugin = (config) => ({
  name: 'html',
  setup(build) {
    build.onResolve({ filter: /\.html$/ }, args => ({
      path: path.resolve(args.resolveDir, args.path),
      namespace: 'html',
    }));
    build.onLoad({ filter: /.html/, namespace: 'html' }, (args) => {
      let htmlContent = fs.readFileSync(args.path).toString('utf-8');

      // replace env vars
      if (config.env) {
        const envPrefix = config.envPrefix || 'REACT_APP_';
        const envVars = Object.entries(process.env || {}).filter(([name]) => name.startsWith(envPrefix));
        htmlContent = envVars.reduce(
          (memo, [name, value]) => memo.replace(new RegExp(`%${name}%`, 'igm'), value),
          htmlContent,
        );
      }

      return {
        contents: htmlContent,
        loader: 'file'
      };
    });

    build.onEnd((result) => {
      const outFiles = Object.keys((result.metafile || {}).outputs);
      const jsFiles = outFiles.filter((p) => p.endsWith('.js'));
      const cssFiles = outFiles.filter((p) => p.endsWith('.css'));
      const htmlFiles = outFiles.filter((p) => p.endsWith('.html'));

      const headerAppends = cssFiles.reduce(
        (memo, p) => {
          const filename = p.split(path.sep).slice(-1)[0];
          return [...memo, `<link href="${filename}" rel="stylesheet">`];
        },
        [],
      );

      const bodyAppends = jsFiles.reduce(
        (memo, p) => {
          const filename = p.split(path.sep).slice(-1)[0];
          return [...memo, `<script src="${filename}"></script>`];
        },
        [],
      );

      for (const htmlFile of htmlFiles) {
        let htmlContent = fs.readFileSync(htmlFile).toString('utf-8');

        // replace env vars
        if (config.env) {
          const envPrefix = config.envPrefix || 'REACT_APP_';
          const envVars = Object.entries(process.env).filter(([name]) => name.startsWith(envPrefix));

          htmlContent = envVars.reduce(
            (memo, [name, value]) => memo.replace(new RegExp(`%${name}%`, 'igm'), value),
            htmlContent,
          );
        }

        // inject references to js and css files
        htmlContent = htmlContent
          .replace('</head>', [...headerAppends, '</head>'].join("\n"))
          .replace('</body>', [...bodyAppends, '</body>'].join("\n"));

        fs.writeFileSync(config.filename.replace('-[^.]+', ''), htmlContent);
      }
    });
  },
});

module.exports = HtmlPlugin;
