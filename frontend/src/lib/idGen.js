export function genTransactionId(taken) {
  let id;
  do {
    id = `txn_${Math.floor(100000 + Math.random() * 899999)}`;
  } while (taken?.has(id));
  return id;
}
