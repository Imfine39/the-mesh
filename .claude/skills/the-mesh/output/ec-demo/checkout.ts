/**
 * checkout - カートの内容で注文を確定
 *
 * Generated from TRIR Spec: ec-demo
 *
 * Post-conditions:
 *   1. Order created with:
 *      - id: generateId()
 *      - userId: input.userId
 *      - totalAmount: calculated from cart items
 *      - status: "PENDING"
 *      - createdAt: now()
 *   2. OrderItems created from CartItems
 *   3. CartItems deleted
 */

import {
  CheckoutInput,
  CheckoutOutput,
  Order,
  OrderItem,
  EmptyCartError,
  CartNotFoundError,
} from './types';
import { RepositoryContext, generateId, now } from './repositories';

export async function checkout(
  input: CheckoutInput,
  ctx: RepositoryContext
): Promise<CheckoutOutput> {
  const { cartId, userId } = input;

  // === Fetch cart ===
  const cart = await ctx.carts.get(cartId);
  if (!cart) {
    throw new CartNotFoundError();
  }

  // === Fetch cart items ===
  const cartItems = await ctx.cartItems.findByCartId(cartId);
  if (cartItems.length === 0) {
    throw new EmptyCartError();
  }

  // === Calculate total amount ===
  const totalAmount = cartItems.reduce(
    (sum, item) => sum + item.unitPrice * item.quantity,
    0
  );

  // === Post-condition 1: Create Order ===
  const order: Order = {
    id: generateId(),
    userId: userId,
    totalAmount: totalAmount,
    status: 'PENDING',
    createdAt: now(),
  };

  await ctx.orders.create(order);

  // === Post-condition 2: Create OrderItems from CartItems ===
  for (const cartItem of cartItems) {
    const product = await ctx.products.get(cartItem.productId);

    const orderItem: OrderItem = {
      id: generateId(),
      orderId: order.id,
      productId: cartItem.productId,
      productName: product?.name ?? 'Unknown',
      quantity: cartItem.quantity,
      unitPrice: cartItem.unitPrice,
    };

    await ctx.orderItems.create(orderItem);
  }

  // === Post-condition 3: Delete CartItems ===
  for (const cartItem of cartItems) {
    await ctx.cartItems.delete(cartItem.id);
  }

  return { order };
}
