import { getStorage } from 'firebase/storage';
import { getFirestore } from 'firebase/firestore';

import { initializeApp } from 'firebase/app';
const firebaseConfig = {
  apiKey: "AIzaSyCiCESWm2ifV15nZIH5bvchAWDwGQD73YI",
  authDomain: "d-earth-f98b9.firebaseapp.com",
  projectId: "d-earth-f98b9",
  storageBucket: "d-earth-f98b9.appspot.com",
  messagingSenderId: "931952539030",
  appId: "1:931952539030:web:c2381c583c56ee13e6d9b7"
};

export const firebaseApp = initializeApp(firebaseConfig);
export const storage = getStorage(firebaseApp);
export const db = getFirestore(firebaseApp);
