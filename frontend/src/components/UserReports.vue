<template>
  <div class="user-reports">
    <h2>Отчеты пользователей</h2>
    
    <!-- Форма для создания отчета -->
    <div class="report-form">
      <div class="form-group">
        <label for="repoLinks">Ссылки на репозитории</label>
        <div class="repo-input-container">
          <input 
            type="text" 
            id="repoLink" 
            v-model="newRepoLink" 
            placeholder="https://github.com/owner/repo"
            class="form-control"
            @keyup.enter="addRepoLink"
            :class="{ 'input-error': errors.repoLink }"
          >
          <button @click="addRepoLink" class="add-repo-btn">Добавить</button>
        </div>
        <div class="error-message" v-if="errors.repoLink">{{ errors.repoLink }}</div>
        <div class="error-message" v-if="errors.repoLinksCount">{{ errors.repoLinksCount }}</div>
        <div class="repo-links-list" v-if="reportForm.repoLinks.length > 0">
          <div v-for="(link, index) in reportForm.repoLinks" :key="index" class="repo-link-item">
            <span>{{ link }}</span>
            <button @click="removeRepoLink(index)" class="remove-link-btn">×</button>
          </div>
        </div>
        <div class="error-message" v-if="errors.repoLinksEmpty">{{ errors.repoLinksEmpty }}</div>
      </div>
      
      <div class="form-group">
        <label for="login">Логин пользователя</label>
        <input 
          type="text" 
          id="login" 
          v-model="reportForm.login" 
          placeholder="Введите логин пользователя"
          class="form-control"
          :class="{ 'input-error': errors.login }"
        >
        <div class="error-message" v-if="errors.login">{{ errors.login }}</div>
      </div>
      
      <div class="form-row">
        <div class="form-group date-group">
          <label for="startDate">Дата начала</label>
          <input 
            type="date" 
            id="startDate" 
            v-model="reportForm.startDate"
            class="form-control"
            :class="{ 'input-error': errors.startDate || errors.dateRange }"
          >
          <div class="error-message" v-if="errors.startDate">{{ errors.startDate }}</div>
        </div>
        
        <div class="form-group date-group">
          <label for="endDate">Дата окончания</label>
          <input 
            type="date" 
            id="endDate" 
            v-model="reportForm.endDate"
            class="form-control"
            :class="{ 'input-error': errors.endDate || errors.dateRange }"
          >
          <div class="error-message" v-if="errors.endDate">{{ errors.endDate }}</div>
        </div>
      </div>
      <div class="error-message" v-if="errors.dateRange">{{ errors.dateRange }}</div>
      
      <button @click="generateReport" class="generate-btn" :disabled="loading">
        {{ loading ? 'Формирование...' : 'Сформировать отчет' }}
      </button>
    </div>
    
    <!-- История отчетов -->
    <div class="reports-history">
      <h3 style="margin-left: 16px;">История отчетов</h3>
      <div class="table-container">
        <table class="reports-table">
          <thead>
            <tr>
              <th>Email пользователя</th>
              <th>Файл</th>
              <th>Дата создания</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(report, index) in reports" :key="report.id || index">
              <td>{{ report.email }}</td>
              <td>
                <button @click="downloadReport(report.id)" class="download-btn">
                  Скачать
                </button>
              </td>
              <td>{{ formatDate(report.created_at) }}</td>
            </tr>
            <tr v-if="reports.length === 0">
              <td colspan="3" class="no-data">Нет доступных отчетов</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'UserReports',
  data() {
    return {
      reportForm: {
        login: '',
        repoLinks: [],
        startDate: '',
        endDate: ''
      },
      newRepoLink: '',
      reports: [],
      loading: false,
      error: null,
      errors: {
        repoLink: null,
        repoLinksCount: null,
        repoLinksEmpty: null,
        login: null,
        startDate: null,
        endDate: null,
        dateRange: null
      }
    };
  },
  mounted() {
    this.fetchReports();
  },
  methods: {
    clearErrors() {
      this.errors = {
        repoLink: null,
        repoLinksCount: null,
        repoLinksEmpty: null,
        login: null,
        startDate: null,
        endDate: null,
        dateRange: null
      };
    },
    
    validateGithubUrl(url) {
      const githubRegex = /^https:\/\/github\.com\/[\w-]+\/[\w.-]+\/?$/;
      return githubRegex.test(url);
    },
    
    addRepoLink() {
      this.errors.repoLink = null;
      this.errors.repoLinksCount = null;
      
      if (!this.newRepoLink || !this.newRepoLink.trim()) {
        this.errors.repoLink = 'Ссылка на репозиторий не может быть пустой';
        return;
      }
      
      const trimmedLink = this.newRepoLink.trim();
      
      if (!this.validateGithubUrl(trimmedLink)) {
        this.errors.repoLink = 'Неверный формат ссылки. Используйте формат: https://github.com/owner/repo';
        return;
      }
      
      if (this.reportForm.repoLinks.includes(trimmedLink)) {
        this.errors.repoLink = 'Такая ссылка уже добавлена';
        return;
      }
      
      if (this.reportForm.repoLinks.length >= 5) {
        this.errors.repoLinksCount = 'Максимальное количество репозиториев: 5';
        return;
      }
      
      this.reportForm.repoLinks.push(trimmedLink);
      this.newRepoLink = '';
      this.errors.repoLinksEmpty = null;
    },
    
    removeRepoLink(index) {
      this.reportForm.repoLinks.splice(index, 1);
      this.errors.repoLinksCount = null;
    },
    
    validateForm() {
      this.clearErrors();
      let isValid = true;
      
      if (this.reportForm.repoLinks.length === 0) {
        this.errors.repoLinksEmpty = 'Добавьте хотя бы одну ссылку на репозиторий';
        isValid = false;
      }
      
      if (!this.reportForm.login || !this.reportForm.login.trim()) {
        this.errors.login = 'Введите логин пользователя';
        isValid = false;
      }
      
      if (!this.reportForm.startDate) {
        this.errors.startDate = 'Укажите дату начала';
        isValid = false;
      }
      
      if (!this.reportForm.endDate) {
        this.errors.endDate = 'Укажите дату окончания';
        isValid = false;
      }
      
      if (this.reportForm.startDate && this.reportForm.endDate) {
        const startDate = new Date(this.reportForm.startDate);
        const endDate = new Date(this.reportForm.endDate);
        
        if (startDate > endDate) {
          this.errors.dateRange = 'Дата начала не может быть больше даты окончания';
          isValid = false;
        }
      }
      
      return isValid;
    },
    
    async fetchReports() {
      this.loading = true;
      try {
        console.log("Запрашиваем список отчетов");
        const response = await axios.get('/api/reports');
        console.log("Получены отчеты:", response.data);
        this.reports = response.data;
      } catch (error) {
        console.error('Ошибка при получении отчетов:', error);
        this.error = 'Не удалось загрузить отчеты';
      } finally {
        this.loading = false;
      }
    },
    
    async generateReport() {
      if (!this.validateForm()) {
        return;
      }
      
      this.loading = true;
      this.error = null;
      
      try {
        alert('Начат процесс формирования отчета. Это может занять некоторое время. Отчет автоматически появится в списке и будет доступен для скачивания.');
        
        const login = this.reportForm.login;
        
        const response = await axios.post('/api/reports/generate', {
          email: this.reportForm.login,
          login: this.reportForm.login,
          repoLinks: this.reportForm.repoLinks,
          startDate: this.reportForm.startDate,
          endDate: this.reportForm.endDate
        });
        
        const processId = response.data.process_id;
        
        this.reportForm = {
          login: '',
          repoLinks: [],
          startDate: '',
          endDate: ''
        };
        this.newRepoLink = '';
        this.clearErrors();
        
        console.log(`Запрос на формирование отчета отправлен. ID процесса: ${processId}`);
        
        const checkStatus = async () => {
          try {
            const statusResponse = await axios.get(`/api/reports/status/${processId}`);
            const { status, message, report_id } = statusResponse.data;
            
            console.log(`Статус формирования отчета: ${status}, сообщение: ${message}`);
            
            if (status === 'completed' && report_id) {
              this.loading = false;
              
              await this.fetchReports();
              
              // Для завершенных отчетов проверяем наличие ошибок анализа
              try {
                const reportResponse = await axios.get(`/api/reports/${report_id}/analysis`);
                
                // Проверяем наличие информации об ошибках в отчете
                if (reportResponse.data && reportResponse.data.error_details) {
                  const errorDetails = reportResponse.data.error_details;
                  let errorMessage = errorDetails.message + "\n\nПричины:\n";
                  
                  // Добавляем каждую причину ошибки в сообщение
                  errorDetails.details.forEach(detail => {
                    errorMessage += `- ${detail}\n`;
                  });
                  
                  errorMessage += "\nРекомендации:\n";
                  errorMessage += "- Убедитесь, что указан правильный логин пользователя на GitHub\n";
                  errorMessage += "- Проверьте доступность указанных репозиториев\n";
                  errorMessage += "- Убедитесь, что в указанном периоде времени есть PR";
                  
                  // Выводим сообщение в alert
                  alert(errorMessage);
                  return true;
                }
              } catch (error) {
                console.log("Информация об ошибках анализа недоступна:", error);
              }
              
              alert(`Отчет для ${login} успешно сформирован и доступен для скачивания!`);
              return true;
            } else if (status === 'failed') {
              this.loading = false;
              
              // Проверяем, содержит ли сообщение об ошибке информацию о PR/репозиториях/авторах
              if (message.includes("не найдены") || message.includes("не существует") || 
                  message.includes("не содержат PR") || message.includes("не найден")) {
                alert(`Ошибка при формировании отчета: ${message}\n\nПроверьте правильность логина и доступность репозиториев.`);
              } else {
                alert(`Не удалось сформировать отчет: ${message}`);
              }
              return true;
            }
            
            return false;
          } catch (error) {
            console.error('Ошибка при проверке статуса отчета:', error);
            return false;
          }
        };
        
        const interval = setInterval(async () => {
          const isDone = await checkStatus();
          if (isDone) {
            clearInterval(interval);
          }
        }, 5000);
        
        setTimeout(() => {
          clearInterval(interval);
          if (this.loading) {
            this.loading = false;
            alert("Превышено время ожидания формирования отчета. Пожалуйста, проверьте список отчетов позже.");
          }
        }, 15 * 60 * 1000);
        
      } catch (error) {
        console.error('Ошибка при запросе на формирование отчета:', error);
        
        let errorMessage = 'Не удалось отправить запрос на формирование отчета';
        
        if (error.response) {
          errorMessage += `: ${error.response.status} - ${error.response.statusText}`;
          if (error.response.data && typeof error.response.data === 'object') {
            errorMessage += `. ${error.response.data.detail || ''}`;
          }
        } else if (error.request) {
          errorMessage = 'Не удалось получить ответ от сервера. Проверьте подключение к интернету.';
        } else {
          errorMessage += `: ${error.message}`;
        }
        
        alert(errorMessage);
        this.error = errorMessage;
        this.loading = false;
      }
    },
    
    async downloadReport(reportId) {
      try {
        const response = await axios.get(`/api/reports/${reportId}/download`, {
          responseType: 'blob'
        });
        
        const blob = new Blob([response.data], { type: 'application/pdf' });
        
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        const fileName = `report_${new Date().toISOString().slice(0, 10)}.pdf`;
        link.setAttribute('download', fileName);
        document.body.appendChild(link);
        link.click();
        
        window.URL.revokeObjectURL(url);
        link.remove();
      } catch (error) {
        console.error('Ошибка при скачивании отчета:', error);
        alert('Не удалось скачать отчет');
      }
    },
    
    formatDate(dateString) {
      if (!dateString) return '—';
      
      try {
        const date = new Date(dateString);
        
        if (isNaN(date.getTime())) {
          console.error('Невалидная дата:', dateString);
          return '—';
        }
        
        const utcTime = date.getTime();
        
        const mskTime = new Date(utcTime);
        
        const formattedDate = new Intl.DateTimeFormat('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        }).format(mskTime);
        
        return `${formattedDate} (МСК)`;
      } catch (error) {
        console.error('Ошибка форматирования даты:', error, dateString);
        return dateString || '—';
      }
    }
  }
};
</script>

<style scoped>
.user-reports {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

h2 {
  margin-bottom: 20px;
  color: #333;
  font-weight: 500;
}

h3 {
  margin: 25px 0 15px;
  color: #444;
  font-weight: 500;
}

.report-form {
  background-color: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 30px;
}

.form-group {
  margin-bottom: 15px;
}

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.date-group {
  flex: 1;
  min-width: 140px;
  max-width: calc(50% - 10px);
}

label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  text-align: left;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.generate-btn {
  display: block;
  width: 100%;
  padding: 12px;
  background-color: #1e88e5;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
}

.generate-btn:hover {
  background-color: #1976d2;
}

.generate-btn:disabled {
  background-color: #90caf9;
  cursor: not-allowed;
}

.reports-history {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.table-container {
  overflow-x: auto;
}

.reports-table {
  width: 100%;
  border-collapse: collapse;
}

.reports-table th,
.reports-table td {
  padding: 12px 15px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.reports-table th {
  background-color: #f8f9fa;
  font-weight: 500;
}

.reports-table tr:last-child td {
  border-bottom: none;
}

.download-btn {
  background-color: #1e88e5;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.download-btn:hover {
  background-color: #1976d2;
}

.no-data {
  text-align: center;
  color: #888;
  padding: 30px 0;
}

.repo-input-container {
  display: flex;
  gap: 10px;
}

.add-repo-btn {
  padding: 10px 15px;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}

.add-repo-btn:hover {
  background-color: #45a049;
}

.repo-links-list {
  margin-top: 10px;
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 5px;
}

.repo-link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background-color: #f5f5f5;
  margin-bottom: 5px;
  border-radius: 4px;
}

.remove-link-btn {
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 50%;
  width: 22px;
  height: 22px;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-link-btn:hover {
  background-color: #d32f2f;
}

.error-message {
  color: #f44336;
  font-size: 12px;
  margin-top: 4px;
  margin-left: 2px;
  text-align: left;
}

.input-error {
  border-color: #f44336 !important;
}
</style>