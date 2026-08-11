import { onRequestGet as __api_data__filename__js_onRequestGet } from "C:\\Users\\T2Hol\\Desktop\\Northstar OS Retail Arbitrage Agent\\functions\\api\\data\\[filename].js"
import { onRequestGet as __api_files_js_onRequestGet } from "C:\\Users\\T2Hol\\Desktop\\Northstar OS Retail Arbitrage Agent\\functions\\api\\files.js"
import { onRequestGet as __api_latest_deals_js_onRequestGet } from "C:\\Users\\T2Hol\\Desktop\\Northstar OS Retail Arbitrage Agent\\functions\\api\\latest-deals.js"

export const routes = [
    {
      routePath: "/api/data/:filename",
      mountPath: "/api/data",
      method: "GET",
      middlewares: [],
      modules: [__api_data__filename__js_onRequestGet],
    },
  {
      routePath: "/api/files",
      mountPath: "/api",
      method: "GET",
      middlewares: [],
      modules: [__api_files_js_onRequestGet],
    },
  {
      routePath: "/api/latest-deals",
      mountPath: "/api",
      method: "GET",
      middlewares: [],
      modules: [__api_latest_deals_js_onRequestGet],
    },
  ]