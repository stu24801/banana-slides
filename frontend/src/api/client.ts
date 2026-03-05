import axios from 'axios';

// 開發環境：透過 Vite proxy 轉發
// 生產環境：透過 nginx proxy 轉發
const API_BASE_URL = '';

// 建立 axios 例項
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5分鐘超時（AI生成可能很慢）
});

// 請求攔截器
apiClient.interceptors.request.use(
  (config) => {
    // 自動帶入 auth token
    const token = localStorage.getItem('bs_auth_token');
    if (token && config.headers) {
      config.headers['X-Auth-Token'] = token;
    }

    // 如果請求體是 FormData，刪除 Content-Type 讓瀏覽器自動設定
    if (config.data instanceof FormData) {
      if (config.headers) {
        delete config.headers['Content-Type'];
      }
    } else if (config.headers && !config.headers['Content-Type']) {
      config.headers['Content-Type'] = 'application/json';
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 響應攔截器
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      // 401 → 清除 token 並重新整理（回到登入頁）
      if (error.response.status === 401) {
        localStorage.removeItem('bs_auth_token');
        window.location.reload();
        return Promise.reject(error);
      }
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      console.error('Network Error:', error.request);
    } else {
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// 圖片URL處理工具
// 使用相對路徑，透過代理轉發到後端
export const getImageUrl = (path?: string, timestamp?: string | number): string => {
  if (!path) return '';
  // 如果已經是完整URL，直接返回
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  // 使用相對路徑（確保以 / 開頭）
  let url = path.startsWith('/') ? path : '/' + path;
  
  // 新增時間戳引數避免瀏覽器快取（僅在提供時間戳時新增）
  if (timestamp) {
    const ts = typeof timestamp === 'string' 
      ? new Date(timestamp).getTime() 
      : timestamp;
    url += `?v=${ts}`;
  }
  
  return url;
};

export default apiClient;

