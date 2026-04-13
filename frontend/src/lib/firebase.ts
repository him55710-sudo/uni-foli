import { initializeApp, type FirebaseApp, type FirebaseOptions } from 'firebase/app';
import { getAuth, GoogleAuthProvider, type Auth } from 'firebase/auth';
import { getFirestore, type Firestore } from 'firebase/firestore';

const viteEnv = ((import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env ??
  {}) as Record<string, string | undefined>;

const firebaseConfig: FirebaseOptions = {
  apiKey: viteEnv.VITE_FIREBASE_API_KEY,
  authDomain: viteEnv.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: viteEnv.VITE_FIREBASE_PROJECT_ID,
  storageBucket: viteEnv.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: viteEnv.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: viteEnv.VITE_FIREBASE_APP_ID,
  measurementId: viteEnv.VITE_FIREBASE_MEASUREMENT_ID,
};

const firestoreDatabaseId = viteEnv.VITE_FIREBASE_FIRESTORE_DATABASE_ID;
// Guest mode is now restricted and should not mimic real authenticated state for protected routes.
export const isGuestModeAllowed = viteEnv.VITE_ALLOW_GUEST_MODE === 'true';

const requiredFirebaseKeys = [
  'VITE_FIREBASE_API_KEY',
  'VITE_FIREBASE_AUTH_DOMAIN',
  'VITE_FIREBASE_PROJECT_ID',
  'VITE_FIREBASE_APP_ID',
] as const;

export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey &&
    firebaseConfig.authDomain &&
    firebaseConfig.projectId &&
    firebaseConfig.appId,
);

export function getFirebaseMissingKeys(): string[] {
  const keyMap: Record<(typeof requiredFirebaseKeys)[number], string | undefined> = {
    VITE_FIREBASE_API_KEY: viteEnv.VITE_FIREBASE_API_KEY,
    VITE_FIREBASE_AUTH_DOMAIN: viteEnv.VITE_FIREBASE_AUTH_DOMAIN,
    VITE_FIREBASE_PROJECT_ID: viteEnv.VITE_FIREBASE_PROJECT_ID,
    VITE_FIREBASE_APP_ID: viteEnv.VITE_FIREBASE_APP_ID,
  };

  return requiredFirebaseKeys.filter(key => !keyMap[key] || !keyMap[key]?.trim());
}

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let db: Firestore | null = null;
let googleProvider: GoogleAuthProvider | null = null;

if (isFirebaseConfigured) {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  db = firestoreDatabaseId ? getFirestore(app, firestoreDatabaseId) : getFirestore(app);
  googleProvider = new GoogleAuthProvider();
  googleProvider.setCustomParameters({ prompt: 'select_account' });
} else {
  console.warn(
    isGuestModeAllowed
      ? 'Firebase config is missing. Guest mode is allowed for local development.'
      : 'Firebase config is missing. Guest mode is disabled in this environment.',
  );
}

export { app, auth, db, googleProvider };
