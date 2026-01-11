/**
 * checkout - カートの内容で注文を確定
 * Generated from TRIR Spec
 */

import {
  Order,
  RepositoryContext,
  generateId,
  now,
} from './types';

interface CheckoutInput {
  cartId: string;
  userId: string;
}

interface CheckoutOutput {
  order: Order;
}

// エラークラス
export class EmptyCartError extends Error {
  code = 'EMPTY_CART';
  status = 400;
  constructor() { super('カートが空です'); }
}

export class CartNotFoundError extends Error {
  code = 'CART_NOT_FOUND';
  status = 404;
  constructor() { super('カートが見つかりません'); }
}

/**
 * カートの内容で注文を確定する
 *
 * @post Order が作成される（status=PENDING）
 */
export async function checkout(
  input: CheckoutInput,
  ctx: RepositoryContext
): Promise<CheckoutOutput> {
  const { cartId, userId } = input;

  // Get cart
  const cart = await ctx.cartRepository.get(cartId);
  if (!cart) {
    throw new CartNotFoundError();
  }

  // Get cart items
  const cartItems = await ctx.cartItemRepository.findByCartId(cartId);
  if (cartItems.length === 0) {
    throw new EmptyCartError();
  }

  // Calculate total amount
  const totalAmount = cartItems.reduce(
    (sum, item) => sum + item.unitPrice * item.quantity,
    0
  );

  // Post-action 1: Create Order
  const order = await ctx.orderRepository.create({
    id: generateId(),
    userId: userId,
    totalAmount: totalAmount,
    status: 'PENDING',
    createdAt: now(),
  });

  // Create OrderItems from CartItems
  for (const item of cartItems) {
    const product = await ctx.productRepository.get(item.productId);
    await ctx.orderItemRepository.create({
      id: generateId(),
      orderId: order.id,
      productId: item.productId,
      productName: product?.name ?? '',
      quantity: item.quantity,
      unitPrice: item.unitPrice,
    });
  }

  return { order };
}
