import { createAccountApplication } from './application/createAccountApplication'
import { HttpAccountRepository } from './infrastructure/http/accountApi'

export const accountApplication = createAccountApplication(new HttpAccountRepository())
