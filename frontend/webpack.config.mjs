import path from "node:path";
import { fileURLToPath } from "node:url";
import webpack from "webpack";
import HtmlWebpackPlugin from "html-webpack-plugin";
import dotenv from "dotenv";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config();

export default (env, argv) => {
  const isProduction = argv.mode === "production";

  return {
    entry: "./src/main.jsx",
    output: {
      path: path.resolve(__dirname, "dist"),
      filename: isProduction ? "assets/[name].[contenthash:8].js" : "assets/[name].js",
      publicPath: "/",
      clean: true,
    },
    mode: isProduction ? "production" : "development",
    devtool: isProduction ? "source-map" : "eval-source-map",
    resolve: {
      extensions: [".js", ".jsx"],
    },
    module: {
      rules: [
        {
          test: /\.jsx?$/,
          exclude: /node_modules/,
          use: "babel-loader",
        },
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
        {
          test: /\.(png|jpe?g|gif|svg)$/i,
          type: "asset",
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        template: "./index.html",
        favicon: "./public/favicon.svg",
      }),
      new webpack.DefinePlugin({
        "process.env.API_BASE_URL": JSON.stringify(
          process.env.API_BASE_URL || "http://localhost:8000"
        ),
      }),
    ],
    devServer: {
      port: 5173,
      open: false,
      hot: true,
      historyApiFallback: true, // client-side routing (react-router BrowserRouter)
      static: {
        directory: path.resolve(__dirname, "public"),
      },
    },
    performance: {
      hints: false, // recharts pushes the single bundle past the default 250kb hint; not worth code-splitting for this app's size
    },
  };
};
