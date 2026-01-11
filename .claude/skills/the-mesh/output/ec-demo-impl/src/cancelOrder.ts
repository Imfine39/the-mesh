/**
 * cancelOrder - 注文をキャンセル
 * Generated from TRIR Spec
 */

import {
  Order,
  RepositoryContext,
  OrderNotFoundError,
  CannotCancelError,
} from './types';

interface CancelOrderInput {
  orderId: string;
}

interface CancelOrderOutput {
  order: Order;
}

/**
 * 注文をキャンセルする
 *
 * @pre order.status == "PENDING"
 * @post Order.status が "CANCELLED" に更新される
 */
export async function cancelOrder(
  input: CancelOrderInput,
  ctx: RepositoryContext
): Promise<CancelOrderOutput> {
  const { orderId } = input;

  // Get order
  const order = await ctx.orderRepository.get(orderId);
  if (!order) {
    throw new OrderNotFoundError();
  }

  // Pre-condition: status must be PENDING
  if (order.status !== 'PENDING') {
    throw new CannotCancelError();
  }

  // Post-action 1: Update order status to CANCELLED
  const updatedOrder = await ctx.orderRepository.update(orderId, {
    status: 'CANCELLED',
  });

  return { order: updatedOrder };
}
