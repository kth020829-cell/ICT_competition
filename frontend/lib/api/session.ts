export interface StudentSession {
  studentId: string;
  studentToken: string;
  nickname: string;
  classId: string;
  classCode: string;
}

export interface TeacherSession {
  teacherId: string;
  name: string;
  email: string;
  classId?: string;
}

const STUDENT_KEY = "dasibom-student-session";
const TEACHER_KEY = "dasibom-teacher-session";

function read<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.sessionStorage.getItem(key);
    return value ? JSON.parse(value) as T : null;
  } catch {
    window.sessionStorage.removeItem(key);
    return null;
  }
}

function write<T>(key: string, value: T | null) {
  if (typeof window === "undefined") return;
  if (value === null) window.sessionStorage.removeItem(key);
  else window.sessionStorage.setItem(key, JSON.stringify(value));
}

export const studentSessionStore = {
  get: () => read<StudentSession>(STUDENT_KEY),
  set: (session: StudentSession) => write(STUDENT_KEY, session),
  clear: () => write(STUDENT_KEY, null),
};

export const teacherSessionStore = {
  get: () => read<TeacherSession>(TEACHER_KEY),
  set: (session: TeacherSession) => write(TEACHER_KEY, session),
  clear: () => write(TEACHER_KEY, null),
};
